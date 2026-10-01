# quality_review —— wfflab__wsync-142

质检日期：2026-10-01　｜　题包版本：**2.1**　｜　质检结论：**FLAG**（2 项证据待补）

> 结论含义：题包本体（结构、题面、判分、对照验证、身份一致性）已通过；
> **镜像 Digest（G1）与 v2.1 多模型区分度（G2）两项证据仍在补齐中**，因此暂不能申报最终验收。
> v1.0 → v2.0 → 2.1 的整改动因、设计与复验见 `remediation_and_retest.md`。

## 一、版本沿革（为什么有 2.0 / 2.1）

v1.0 的 16 条 required 对主流模型过于宽松：Opus 5 三次全部 1.0（`model_score_sum = 3.0`），
Qwen3.8-Max-0902 与 Kimi K3 亦为 1.0。按规范 8.2，`Opus.model_score_sum > Qwen.model_score_sum`
与「双 0 且 Opus 的 `testcase_pass_sum` 更大」两个准入条件**均不成立** →
区分度不满足准入要求，须**整改或替换**。

整改方向：**整体提高题目难度**（而非换题）。required 由 16 条（F2P 7 + P2P 9）扩到 **24 条（F2P 15 + P2P 9）**，
新增的 8 条 F2P 全部来自**实测确认的 Windows 文件系统语义**（见 `scripts/win_probe.py` 12 条假设，11 命中）。
`task_version` 由 `1.0` → `2.0`，`task_hash` 随之变更（`ec4941c1…`）；
随后因迭代 5 修正两条超出题面的用例，`task_hash` 最终为 **`478e5057…`**（`task_version` 2.0 → **2.1**）。

## 二、已完成并通过的检查

| 检查项 | 结论 | 证据 |
|---|---|---|
| Windows 价值反事实判定 | PASS | `metadata/labels.json` windows_mechanism；五类根因均只在 Windows 语义下成立（换 Linux 后实现/根因/Evaluator 均变） |
| 标准 Harbor 五件套 | PASS | `task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/` + `platform_import.json` + `extras/` |
| task.toml Schema 1.3 关键字段 | PASS | version / [metadata] / [agent] / [verifier] / [environment] / 资源 / 超时 ≤12h |
| 题面不泄漏解法 | PASS | `instruction.md` 无 Golden/Oracle/隐藏测试/F2P-P2P/Reward 表述；只给现象与验收标准 |
| 题面不新增未声明要求 | PASS | 目标 4（类型冲突清障）与目标 5（内容级变更判定 + mtime 保真 + 幂等）在题面明写，逐条覆盖新 required |
| environment 不泄漏答案 | PASS | `environment/workspace/` 仅含被测包源码与自带测试，无 solution/隐藏测试 |
| 题面 ↔ testcase 双向映射 | PASS | `testcase_mapping.csv` R1–R24，每条 required 可追溯到题面章节或既有兼容性要求 |
| 二值判分 | PASS | `grade.py`：required F2P + P2P 全过 = 1.0，否则 0.0；无权重、无部分分、无 LLM Judge |
| INVALID ≠ 0 分 | PASS | 缺失/SKIP/解析失败 → 不写 reward 产物并 exit 2；候选编译失败才计合法 0 分 |
| no-change 3 次全 0 | PASS | `evidence/no_change/run-1..3`：score 均 **0.0**，pytest **9/24**（P2P 全过、15 条 F2P 全失败） |
| Golden 3 次全 1 | PASS | `evidence/golden/run-1..3`：score 均 **1.0**，pytest **24/24**，无 SKIP / MISSING / ERROR |
| 干净重建复验 | PASS | `evidence/clean_room/`：清空全部中间目录后重建，no-change=**0.0**（9/24）、golden=**1.0**（24/24） |
| 反例覆盖（3 类） | PASS | `negative_01_readonly_only` **0.0**（17/24）、`negative_02_swallow_errors` **0.0**（22/24）、`negative_03_force_clean_target` **0.0**（20/24） |
| 接受等价实现 | PASS | `equivalent_01_alternate_impl`（scandir + sha256 + 临时文件原子替换，完全不同的 API 与控制流）得 **1.0**（24/24） |
| 用例不超出题面 | PASS（**经真实运行反查后修正**） | 迭代 5：两条大小写用例原先把"终态用源侧还是目标侧大小写"写死，超出题面声明；已改为大小写不敏感断言，Opus 5 `run-1` 由 18/24 → 19/24。详见 `remediation_and_retest.md` |
| 副作用可清理 | PASS | `evidence/cleanup_and_restore/README.md`：不涉及系统级副作用，13 个中间目录全部清理成功 |
| 可见测试未被破坏 | PASS | base 与 oracle 下 `tests/test_wsync_basic.py` 均 **7 passed** |
| 身份三元组一致 | PASS | task.toml / swelive_spec.json / platform_import.json / manifest.json 四处均为 `2.1` + `478e5057…` |
| 官方校验器 `validate_package.py` | **PASS 256 / FAIL 0 / FLAG 0** | 退出码 0；机器报告 `_index/validate-report.json` |
| 校验和清单 | PASS | `_index/checksums.sha256` 收录 **446** 个文件，与磁盘应收录数（排除 `__pycache__/`、`*.pyc`、清单自身、`extras/model_runs/_judge/`）**逐条相等** |

## 三、证据缺口（阻塞验收）

| # | 缺口 | 影响 | 补齐方式 |
|---|---|---|---|
| G1 | **镜像未构建，`image_digest` 为空** | 无法证明“同一镜像 Digest”下运行；规范 5.5 要求标签之外另存不可变 Digest | 在 Windows 构建机执行 `docker build` 后，把 digest 回填 `_index/EXTERNAL_IMAGES.json` 与 `metadata/manifest.json`（本机 Docker 未启用 Windows 容器模式） |
| G2 | **v2.1 多模型区分度验证进行中** | 规范第八章准入（Qwen/Opus 各 3 次 + GLM/Kimi 各 ≥1 次）结论未出 | Opus 3/3、Kimi 1/1、GLM 1/1 已完成并判分；Qwen run-1 已产出、run-2/3 仍在跑。全部结束后 `run_model_validation.py --score-only` 出结论 |

### 关于缺口的诚实说明

- 本地对照验证是在**真实 Windows（Windows 11 23H2, x64）**上、以**与 `test.ps1` 等价的判定流程**
  （还原 → 应用补丁 → 环境预检 → 清产物 → 运行 → `grade.py` 评分 → 产物完整性校验）执行的，
  运行环境为 Python 3.13.12 / pytest 8.3.5（与镜像声明的 3.12.9 同主版本）。
  **它不是容器内验证**，因此不能替代 G1 要求的镜像级复现。
- v1.0 关闭前的多模型快照（Opus ×3、Qwen run-1、Kimi 均 1.0，GLM INVALID）留存于
  `_v1_model_runs_snapshot.json`，作为「整改而非替换」的依据。
- v1.0 的 GLM INVALID **并非模型能力不足**，而是端点配置缺陷（方舟端传 `thinking` 字段会导致
  thinking 吃光 `max_tokens`、正文恒空）。根因与修正见 `_index/known_issues.md` 的 K7。

## 四、真实模型运行结果（2.1，本机 L2 判分）

同一份题包、同一 40 步 agent 预算（与 v1.0 相同），在真实 Windows 上按 `test.ps1` 等价流程判分：

| 模型 | 运行 | 状态 | 正式分 | pytest | 备注 |
|---|---|---|---|---|---|
| Opus 5 | run-1 | VALID | **0.0** | 19 / 24 | 未提交（用满 40 步） |
| Opus 5 | run-2 | VALID | **0.0** | 20 / 24 | 已提交，30 步 |
| Opus 5 | run-3 | VALID | **0.0** | 22 / 24 | 已提交，19 步 |
| Kimi K3 | run-1 | VALID | **1.0** | 24 / 24 | 用满 40 步 |
| GLM-5.3 | run-1 | VALID | **1.0** | 24 / 24 | 用满 40 步 |
| Qwen3.8-Max-0902 | run-1..3 | 进行中 | — | — | run-1 已产出补丁 |

**Opus 的失败高度可复现**，三次全部栽在同一族用例（文件 ↔ 目录类型冲突）：

```
test_case_only_difference_between_file_and_directory        3/3 失败
test_target_file_replaced_by_source_directory               3/3 失败
test_target_directory_replaced_by_source_file               2/3 失败
test_conflict_cleanup_keeps_unrelated_readonly_entries_intact 2/3 失败
test_sync_is_idempotent_and_preserves_source_mtime          1/3 失败
```

失败形态也一致：删掉了冲突的旧条目，但**没有按源的类型重新落地**（`assert (target/"bundle").is_dir()`
为 False、`files_under(target)` 只剩空）；另有两轮在删除阶段报
`WinError 3 系统找不到指定的路径`（先删了父目录再去删其子项）。这属于
**能力缺口而非环境噪声**：题目可解（Kimi 与 GLM 均 24/24 满分），Opus 缺的正是本次新增
「目标结构要给文件让位」这条 required。

> 结论：v2.1 相对 v1.0 的区分度改善是真实且可复现的 —— v1.0 时 Opus 三次全 1.0，
> 现在同预算下三次全 0.0。最终准入判定待 Qwen 三次跑完后按规范 8.2 计算。

## 五、v2.1 难度抬升的实证

| 新增 required（8 条 F2P） | 实测 Windows 语义依据 | v1 解法是否失败 |
|---|---|---|
| 只读空目录必须被清掉 | `os.rmdir` 只读目录 → `PermissionError` WinError 5 | 失败 |
| 仅大小写差异的文件 ↔ 目录冲突 | `os.makedirs` 撞同名文件 → `FileExistsError` WinError 183 | 失败 |
| 目标文件被源目录取代 | `open(...,'wb')` 目标为目录 → `PermissionError` | 失败 |
| 目标目录被源文件取代（含只读） | `os.rmdir` 非空 + 只读 → WinError 5 | 失败 |
| 冲突清理不得误伤无关只读条目 | 需按路径精确清障，不能整树清空 | 失败 |
| 同尺寸同 mtime 但内容不同须更新 | `shutil.copyfile` 不保留 mtime → 时间戳不可作判据 | 失败 |
| 幂等 + 保真源 mtime | 需显式 `os.utime` 对齐 | 失败 |
| 只读/被占用条目须上报而不中断 | WinError 5 可修 / WinError 32 不可修，须区分 | 失败 |

> v1 的 oracle 在 v2 的 required 集上**失败 7 条**（上表除最后一条外全部），
> 即「只做局部修补」的解不再能拿满分 —— 这是区分度的直接来源。

## 六、Hack 与答案泄漏审查（四层分级）

| 通道 | 分级 | 依据 |
|---|---|---|
| 联网搜索/下载上游答案 | none | 被测包为构造代码，上游不存在对应答案；运行期 air-gapped |
| 读取本地 Solution / 隐藏测试 / 旧制品 | none | Agent 可见范围内无 `solution/`、无 `test_patch.diff`；工作区 git 历史仅 baseline commit |
| 篡改 Tests / Verifier / 结果文件 | none | `tests/` 位于 `C:\tests`，不在 Agent 工作区内；`grade.py` 只读 `C:\testbed` 产物 |
| 复用旧二进制 / 伪造 PASS | none | 每次运行前 `test.ps1` 删除 `reports/` 与 verifier 产物；评分要求 required 全观测到 |

> `negative_02_swallow_errors`（把失败条目静默吞掉并计为成功）与
> `negative_03_force_clean_target`（同步前清空目标目录以回避冲突）是**针对本类题最可能出现的两种取巧**，
> 实测均为 0.0，证明判分不能被这两类 hack 骗过。
> ⚠️ 规范明确“关键词未命中 ≠ 绝对无 Hack”，**模型运行阶段的动态审查在 G2 补齐时一并完成**。

## 七、题面与测试公平性复核

- 每条 F2P 都能从 `instruction.md` 的“目标/验收标准”推出；不存在未声明要求或事后新增契约。
- 测试只断言**系统终态与公共返回值**（文件存在性、内容、mtime、`SyncResult.failed`），
  不断言私有函数名、参数个数、调用顺序或代码文本；`equivalent_01` 实测 1.0 即为例证。
- 题面显式排除不考察项（NTFS 备用数据流、重解析点、符号链接、目录联接），避免把平台冷知识当难度。
- 难度来自**跨模块状态 + 文件系统语义辨析 + 幂等性**（只读 vs 占用两类 `PermissionError` 的不同处置、
  文件↔目录类型冲突的多层清障、内容级变更判定），不来自歧义或信息缺失。
