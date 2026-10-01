# remediation_and_retest —— wfflab__winstall-210

> 本题是**第二个替换候选**。前序：`wfflab__wsync-142`（门槛不成立，已封存）→
> `wfflab__wproc-209`（门槛待定）→ 本题。
> 最后更新：2026-10-01

## 迭代 1 —— 为什么要换方向（2026-10-01 晚）

### 已实测到的模型行为

| 题包 | Opus 5 | Qwen3.8-Max-0902 | 辅助模型 |
|---|---|---|---|
| `wfflab__wsync-142` | 0.0 / 0.0 / 0.0（19、20、22 / 24） | 1.0 / 0.0 / 0.0（24、23、23 / 24） | GLM 1.0、Kimi 1.0 |
| `wfflab__wproc-209` | 0.0 / 0.0 / 0.0（各 12/13） | 运行中 | GLM 1.0、Kimi 1.0 |

`wproc-209` 上 Opus 三轮失手的是**同一条** F2P：

```
assert "finisher-out" in result.text()
E   AssertionError: assert 'finisher-out' in ''
```

即「直接子进程已正常结束、后代仍持有输出管道」时，`timed_out` 与退出码都判对了，
**唯独把已写出的输出丢空了**。根因是 Opus 用了 `proc.stdout.read(4096)`（阻塞读到读满），
而 Kimi 用 `stream.read1(65536)`（读多少算多少）。

### 关键排查：先怀疑端点，再怀疑题目

两个辅助模型（GLM-5.3、Kimi K3）在两题上都拿 1.0，而 Opus 两题都是 0.0 —— 这个反差
必须先排除"Opus 端点被降级"这一基础设施因素，否则任何选题都是白费。

用 `%TEMP%\wff-probe\endpoint_probe.py` 对四个端点发同一组可精确判分的问题：

| 模型 | 得分 | 其中 W1（`read(n)` 在孙进程持管道时是否阻塞） |
|---|---|---|
| **Opus 5** | **5/5** | **答对**：`BLOCK`，理由是孙进程仍持有写端，管道不会 EOF |
| Kimi K3 | 5/5 | 答对 |
| Qwen3.8-Max | 4/5 | `max_tokens` 截断（探针只给 2048，被思考吃光） |
| GLM-5.3 | 4/5 | 同上（方舟端强制 thinking） |

**结论：端点正常，选项 C 排除。Opus "知道"那条管道语义，只是在 agentic 执行时没用上。**
因此这是**执行细致度**问题，不是知识缺失，也不是基础设施故障。

### 由此确定的方向约束

第三题的难度**不能再压在 Opus 的两个已实测盲区上**：

1. 缓冲流的读取语义（`read(n)` vs `read1(n)`）；
2. 动作创建 / 删除的先后顺序规划。

## 迭代 2 —— 选定「构建、安装与打包」并先实测其 Windows 语义

### 方向选择

| 候选方向 | 取舍 |
|---|---|
| #8 网络与 IPC（Named Pipe） | 放弃。管道的读取/生命周期正是 Opus 的盲区 |
| #2 原生开发与互操作（ctypes/COM） | 放弃。属于"冷门 API 单点"，命中规范 8.2 红线 |
| **#9 构建、安装与打包** | **采用**。难度落在**事务一致性推理**上，而不是低层 API 细节 |

### 先实测，后出题（`skills/harbor-windows/scripts/win_probe_install.py`）

出题前先把依赖的 Windows 行为测准，6 条假设 5 命中 + 1 条刻意的"反直觉发现"：

| 假设 | 结果 | 实测证据 |
|---|---|---|
| c1 目标被只读句柄打开 → 原子替换失败 | **HIT** | `PermissionError winerror=5`（**不是** 32） |
| c2 普通 `copyfile` 是否也被挡住 | **HIT** | **不被挡** → 必须把写入做成原子替换，才能暴露"被占用" |
| c3 句柄释放后原子替换成功 | HIT | 内容变成新内容 |
| c4 替换失败后旧内容保留，但**残留临时文件** | HIT | `内容=b'old' 残留=['target.dll.winstall-part']` |
| c5 目标位置是目录时也失败 | HIT | `winerror=5`、`isdir(dst)=True` |
| c6 两种失败的 winerror 是否可区分 | **MISS** | **都是 5** → 不能靠错误码分流，只能看目标当前是什么 |

**c6 的 MISS 就是本题的核心陷阱**：`_is_deferrable()` 必须用
`os.path.isdir(dst) or not os.path.isfile(dst)` 先排除硬失败，
再判 `PermissionError` + `winerror in (5, 32, 33)`。只抄错误码会直接判错一半场景。

## 迭代 3 —— 建成题包并跑通 L2

### 被测缺陷（base）

| # | 位置 | 缺陷 | 现象 |
|---|---|---|---|
| D1 | `winstall/versions.py` | `compare_versions` 用**字符串**比较数字段 | `1.10.0` 被判为低于 `1.9.0` → 降级被放行 |
| D2 | `winstall/transaction.py` | 原子替换失败直接向上抛，没有"可延迟"路径 | 一个文件被占用 → 整次安装崩 |
| D3 | `winstall/transaction.py` | 没有备份与回滚 | 中途失败后旧版本被覆盖内容破坏、新建文件留在盘上 |

### 参考解（`solution/oracle.patch`，LF / `git diff` 格式）

- `versions.py`：新增 `_segments()`，数字段转 `int` 并补齐四段；预发布标签单独比较
- `transaction.py`：新增 `_is_deferrable()`、`_backup()`、`_restore()`、`_drop_temporaries()`；
  `apply_transaction` 改为「暂存区 + 逆序回滚」，可延迟失败记入 `deferred` 并写入清单
  `pending_replace`，硬失败抛 `ApplyFailed` 并整体回滚

### 14 条 required（7 F2P + 7 P2P）

**F2P**

1. `test_version_segments_compare_numerically_not_lexically`
2. `test_downgrade_is_rejected_and_current_install_is_intact`
3. `test_locked_payload_file_is_deferred_instead_of_aborting`
4. `test_deferred_file_is_completed_by_the_next_apply`
5. `test_failed_upgrade_restores_overwritten_file_bytes`
6. `test_failed_upgrade_removes_newly_created_files`
7. `test_failed_upgrade_leaves_no_temporary_files`

**P2P**

8. `test_clean_install_writes_payload_and_records_version`
9. `test_upgrade_overwrites_payload_and_records_new_version`
10. `test_upgrade_drops_files_absent_from_the_new_version`
11. `test_uninstall_removes_payload_and_manifest_entry`
12. `test_machine_and_user_scopes_do_not_interfere`
13. `test_planning_does_not_touch_the_filesystem`
14. `test_unrelated_products_are_left_untouched`

### 本地复核结果

```
base    : 7 failed / 7 passed   ← 失败的正好是全部 F2P
golden  : 25 passed（11 可见 + 14 隐藏）
L2 nochg: status=VALID score=0.0 pytest_rc=1 (3.0s)
L2 gold : status=VALID score=1.0 pytest_rc=0 (3.0s)
```

三条 F2P 的失败点互不相同、且各自独立对应一处缺陷，不存在"一条测试同时打三处"：

| F2P 组 | 只由哪个缺陷导致 |
|---|---|
| 1、2 | D1（版本比较） |
| 3、4 | D2（没有延迟替换） |
| 5、6、7 | D3（没有回滚 / 没有清理临时文件） |

## 迭代 4 —— 待补

- 对照证据矩阵（`extras/evidence/`：no-change ×3 / Golden ×3 / clean_room / 3 反例 / 等价实现）
- 四路模型验证与规范 8.2 门槛判定
- 镜像构建与 `image_digest` 回填

## 遗留整改

| # | 项 | 说明 |
|---|---|---|
| 1 | 镜像未构建 | 本机 Docker 未启用 Windows 容器模式，`image_digest` 仍为 `PENDING_BUILD` |
| 2 | 对照证据矩阵未生成 | 待 `build_evidence.py`；本题用例无时限断言，可与模型运行并行 |
