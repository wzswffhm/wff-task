# 会话交接文档 — wff-task Windows 题池返修（2026-10-14）

> 用途：在另一台电脑上继续这次工作。本文件是**唯一的上下文入口**，先读它。
> 配套内容：同目录下的 `harbor-windows/` 完整工作树（题包、跑分现场、门禁脚本）。

---

## 0. 一句话现状

| 槽位 | 状态 |
|---|---|
| **215** | ✅ **已完成并上线**。原 `wfflab__wfmt-215`（平台无关的容器格式题）已替换为 `wfflab__wsparse-215`（Windows/NTFS 稀疏文件），`windows-harbor-qc` 结论 **PASS**（5/5），飞书记录 `reczz28KwEOO3xHy` 已更新 |
| **218** | 🚧 **半成品**。`wfflab__wlogseg-218`（同样是平台无关题）正在替换为 `wfflab__wspawn-218`（Windows 子进程句柄继承）。骨架、缺陷模块、隐藏套件、评分链、参考解都已落盘；**还差 8 步**（见 §5） |
| 216 / 219 | 未动。216 与 215/218 是同一毛病（自认通用编码题）；219 有真实 Windows 价值（PE + imagehlp） |

**工作的核心约束（甲方口径，全程适用）**
1. 题目必须**依赖 Windows 专属机制**，或按真实分类移出 Windows 池；**不得只改题名/标签**（返修原因 R5）。
2. `run_tests.ps1` 必须区分 **INVALID（缺测/执行故障）与 FAIL（功能失败）**，INVALID 不得输出正式 0 分（R6）。
3. job 的 `task_checksum` 必须绑定当前交付包；冻结新版后**整批重跑**（R2）。
4. **答案不得写在题面上，不得有引导性注释。**
5. 本批只跑 **Qwen×3 + Opus×3**（不跑 GLM/Kimi）；`jobs/` 共 **12** 个（6 模型 + 3 Oracle + 3 NOP）。
6. 不替用户提交；只在明确路径暂存。

---

## 1. 环境与工具（家里电脑需自备）

| 项 | 值 |
|---|---|
| 仓库根 | `C:\Users\Administrator\Desktop\wff-task` |
| 工作树 | `harbor-windows\`（题包 + `_qc_runs\` 跑分现场 + `skills\` + `_reference\`） |
| Harbor CLI | `C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe`（**不在 PATH**，用时要么加 PATH 要么全路径） |
| DSH Python | `C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe` |
| Docker | 必须切到 **Windows Containers**（context `desktop-windows`）；基础镜像 `mcr.microsoft.com/windows/servercore:ltsc2022` 已缓存 |
| lark-cli | `C:\nvm4w\nodejs\lark-cli.ps1`；Base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA` |
| 凭据 | `models.local.json`（仓库根，**含明文 key，未打进本包**）。家里电脑需要自己放一份；Opus 端点是 `https://4router.net`，模型名必须是 **`claude-opus-5`**（Harbor 的 `ALIASES` 只认这个名字） |

**每次都设**：`$env:PYTHONIOENCODING='utf-8'`

---

## 2. 215 已完成：`wfflab__wsparse-215`

### 2.1 选题依据
公开上游缺陷 **CPython issue 39910《os.ftruncate on Windows should be sparse》**（reporter Mingye Wang，2020-03-09，status open）。容器内实测该缺陷在 Python 3.12.9 上依然存在：

```
os.truncate(64MB): st_size=67108864 compressed=67108864 sparse_bit=False
fsutil queryflag: This file is NOT set as sparse
```

同一行代码在 Linux 上扩展天然稀疏 ⇒ 缺陷只在 Windows/NTFS 上成立。

### 2.2 机制与判据（全部容器实测）
| 场景 | 实测 |
|---|---|
| 先置稀疏标志再 `SetEndOfFile(64MB)` | `AllocationSize=0` |
| 之后写 4096@0 与 8192@32MB，`FlushFileBuffers` | `AllocationSize=131072` |
| `FSCTL_QUERY_ALLOCATED_RANGES` | `[(0,65536),(33554432,65536)]` |
| `fsutil sparse queryflag` | `This file is set as sparse` |
| 密集之后**补设**稀疏标志 | 标志置位但 `AllocationSize` 仍 67108864 ⇒ **不可回溯**（MS-FSCC: currently allocated clusters SHOULD NOT be deallocated） |
| 目录句柄上发 `FSCTL_SET_SPARSE` | `err=87` |

**测量纪律**：写入后必须 `FlushFileBuffers` 或关闭重开句柄，否则分配元数据滞后。

### 2.3 结果
- 门禁 `check_windows_mechanism.py` **F1–F6 全过**
- 控制：Oracle 3×1、NOP 3×0；模型：Qwen [1,0,1]=**2**（testcase 58）、Opus [1,1,1]=**3**（testcase 60）⇒ 区分度**双条件**满足
- 12 job 的 `task_checksum` 唯一 = `575341f7d6aff81bc358b125e31d8fa12090c8f1743f9c630fd9677ca056688f`
- `windows-harbor-qc`：交付目录 / 模型门禁 / 模型 jobs / Oracle-NOP / 十项人工复核 **全 PASS**
- ZIP sha256 `e7ee8983f58d902a97653062f4cb540ec42b5c18839fe616e52ef46fd63862e3`，54,422,706 B
- 飞书记录 `reczz28KwEOO3xHy` 已更新（附件 token `M6pSbHpgUo6kuBx98LKcN7h8nfb`）

### 2.4 排掉的 5 个基础设施坑（**再做新题会全部复现，务必记住**）
1. **稀疏文件穿不过容器层**：构建期生成稀疏样本会让 `hcsshim::ImportLayer` 失败（`The system cannot find the path specified. (0x3)`）。⇒ 不随包提供稀疏样本，fixture 由评测器自己建。
2. **Harbor 只在 verifier 阶段把 `tests/` 挂到 `C:\tests`**，**不挂** `verifier/`。⇒ 隐藏套件必须随包发到 `tests/`，且 `run_tests.ps1` 的候选根要含 `C:\tests`；两副本必须逐字节一致。
3. **Oracle 载荷必须随 `solution/` 交付**：Harbor 的 oracle agent 只上传 `solution/`。⇒ 参考解放 `solution/reference/<pkg>/`；`solve.ps1` 还要能把工作目录解析到 `C:\testbed`。
4. **Windows 注册表代理劫持模型请求**：`HKCU\...\Internet Settings` 的 `ProxyServer=127.0.0.1:7897`（`ProxyEnable=0`）会被 Python `urllib` 读取，导致 Opus 全部 502「所有凭据均已禁用」。⇒ 模型轮脚本显式设 `no_proxy=*` / `NO_PROXY=*`。
5. **残留 Harbor 进程争抢 `jobs-dir`**：`job_kill` 是异步的，残留进程会把正在跑的 trial 写坏（trajectory 停在半路、无 exception、`n_completed=0`）。⇒ 重跑前按 PID 强杀 `harbor` 与其 python 子进程，并确认无容器。

---

## 3. 218 半成品：`wfflab__wspawn-218`

### 3.1 为什么是这个主题（查重结论）
在 158 条飞书记录上扫过全部候选机制族：

| 机制族 | 结论 |
|---|---|
| 文件 ID / 硬链接 / 文件身份 | ✗ 严重占用（`win-fileid-017`、`windows-powershell-file-identity-003`、`windows-ntfs-hardlink-dedupe-002`、`win-hardlink-003`、`windows-hardlink-isolation-002`、`windows-file-hardlink-001`…） |
| Job Object | ✗ `win-job-005` |
| 保留名 / 设备名 / 长路径 | ✗ `win-safe-materialization` 等 |
| USN | ✗ `win-env-008` 等 3 处 |
| 注册表变更通知 | 未见直接占用，但注册表族拥挤 |
| **进程句柄继承（`bInheritHandles` + `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`）** | ✅ **零命中** |
| `CancelIoEx` / 符号链接特权 | ✅ 零命中 |

> ⚠️ 我最初设计的是「文件 ID」题，被 `win-fileid-017` 完整占用（其题面明确要求 16 位大写十六进制 file_id、硬链接同 id、重解析点拒绝），已放弃。**换主题前必须先跑这个查重。**

### 3.2 容器实测判据（`_qc_runs/whandle-build/probe-handle-parent.py`）
```
1. CreatePipe 默认 inherit=False；SetHandleInformation(INHERIT) 可置 True
2. bInheritHandles=TRUE 且不给属性列表 → 子进程 A、B 两个句柄都能写   ← 全部可继承句柄泄漏
3. 给出 PROC_THREAD_ATTRIBUTE_HANDLE_LIST=[w5] → 子进程只有 A 能写，B 完全无输出
4. 句柄值跨进程保持（w5=520 / w6=516）
```

关键性质：**Python 的 `subprocess.Popen` 无法表达句柄列表**，正确解必须直接用 `CreateProcessW` + `STARTUPINFOEX` ⇒ 机制上保证「必须依赖 Windows」。

### 3.3 题目设计
| 项 | 内容 |
|---|---|
| 场景 | 沙箱启动器：子进程**只**应拿到明确列出的句柄 |
| API | `spawn(argv, inherit=[...])` / `set_inheritable(h,on)` / `is_inheritable(h)` / `inheritable_handles()` / `handle_kind(h)` / `WSpawnError` |
| 缺陷版 | `Popen(close_fds=False)` 且**丢弃** `inherit`；`inherit.py` 把 OS 句柄当 fd 交给 `os.set_inheritable`；`kinds.py` 恒 `"unknown"`；`inheritable_handles()` 恒 `[]` |
| 反事实 | POSIX 是「默认不继承 + `FD_CLOEXEC` opt-in」，Windows 是「默认继承 + 属性列表 opt-out」，无对等物 |

### 3.4 已落盘的文件
```
wfflab__wspawn-218-v1.0.0-delivery/
  task.toml  instruction.md  source.json
  environment/{Dockerfile,adapter.toml,agent_visible_paths.json,prepare/run/restore/cleanup.ps1,vendor/,workspace/}
  environment/workspace/{README.md,pyproject.toml,docs/NOTES.md,wspawn/*.py,tests/test_wspawn_basic.py}
  tests/{run_tests.ps1,test.ps1,test.bat,aggregate_results.ps1,required_testcases.json,rubric.json,test_wspawn_semantics.py}
  solution/{solve.ps1,solve.bat,README.md,reference/wspawn/*.py}
  verifier/{README.md,ISOLATION.md,negative_access_probe.ps1,tests/test_wspawn_semantics.py,oracle/{solve.ps1,solve.bat,README.md,reference/wspawn/*.py}}
```
- 隐藏套件 **14 条**（F2P 7 / P2P 7），两副本已校验一致
- 参考解两副本一致，`py_compile` 通过
- `rubric.json` sha256 = `da7d42fab5a90a09f901bfe4403acd804c474b25bd083bacf57d4c470e93739b`

---

## 4. 常用命令（复制即用）

```powershell
$env:PYTHONIOENCODING='utf-8'
$py  = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$hw  = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows'
$harbor = 'C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe'
```

**Windows 机制门禁**（F1–F6）
```powershell
& $py "$hw\skills\harbor-windows\scripts\check_windows_mechanism.py" --task-dir "$hw\wfflab__wspawn-218-v1.0.0-delivery"
```

**整体质检（单包）**——用 junction 造一个只含该包的根目录再跑：
```powershell
& $py "$hw\skills\harbor-windows\scripts\validate_package.py" --package <只含该包的根目录>
```

**手工端到端验证**（建镜像 + NOP/Oracle）：
```powershell
$pkg='...\<package>'; $img='outside-harbor/wfflab__wspawn-218:1.0.0'
docker --context desktop-windows build -t $img -f "$pkg\environment\Dockerfile" "$pkg\environment"
# NOP（期望 0）
docker --context desktop-windows run --rm -v "$pkg\tests:C:\tests:ro" -v "$pkg\verifier:C:\verifier\wfflab__wspawn-218:ro" $img powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& 'C:\tests\test.bat'"
# Oracle（期望 1）
docker --context desktop-windows run --rm -v "$pkg\tests:C:\tests:ro" -v "$pkg\verifier:C:\verifier\wfflab__wspawn-218:ro" -v "$pkg\solution:C:\solution:ro" $img powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& 'C:\solution\solve.ps1'; & 'C:\tests\test.bat'"
```

**12 个 Harbor job + 组装 + 打包**（脚本在 `_qc_runs\wsparse-build\`，218 需把里面的 `wsparse`/215 换成 `wspawn`/218 或另建一份）：
```powershell
& $py "$hw\_qc_runs\wsparse-build\run_wsparse_controls.py" --rounds 3
& $py "$hw\_qc_runs\wsparse-build\run_wsparse_model_rounds.py" --max-steps 40
& $py "$hw\_qc_runs\wsparse-build\assemble_wsparse_harbor_jobs.py"
& $py "$hw\skills\harbor-windows\scripts\package_task_zip.py" --task-dir $pkg --out-dir <out>
```
> **跑分前必须确认 `$pkg\jobs` 不存在**，否则 task checksum 会被污染。

**甲方全量质检**（需要 harbor 在 PATH）：
```powershell
$env:PATH = 'C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts;C:\Program Files\Docker\Docker\resources\bin;' + $env:PATH
& $py "$hw\_reference\windows-harbor-qc\scripts\run_delivery_qc.py" --input <zip> --out <qc-dir> --attempts 3 --quality-review <quality-review-filled.json>
```

---

## 5. 218 还差的 8 步

1. **`metadata/windows_mechanism.json`**：`counterfactual.answer="否"`、`exclusive_declaration.quote`（逐字取自 `instruction.md` 的「本任务的目标平台是真实的 Windows，验收不使用其他操作系统，也不需要实现其他操作系统的版本。」）、**5 条机制锚点**（每条 `instruction_quote` 逐字 + `test_ref` + `f2p_case`）、`non_windows_must_fail`（指向重写后的 `validate_environment.ps1`，evidence 需含 `Win32NT` 等关键字）。
   已算好的行号（`verifier/tests/test_wspawn_semantics.py`）：
   `test_unlisted_handle_does_not_cross_the_boundary`=256、`test_empty_inherit_leaks_nothing`=266、`test_only_one_of_two_handed_over_pipes_crosses`=289、`test_cleared_inherit_flag_keeps_the_object_at_home`=318、`test_set_inheritable_changes_the_observed_flag`=350、`test_is_inheritable_matches_the_observed_flag`=366、`test_handle_kind_classifies_pipe_and_file`=383
2. **`verifier/rubric.conditions.json`**：与 `rubric.json` 的 5 组一一对应，写清每组的 Windows 机制。
3. **`tests/judge.toml`**：`source_sha256 = "da7d42fab5a90a09f901bfe4403acd804c474b25bd083bacf57d4c470e93739b"`，`[[rubrics]]` 5 条与 `rubric.json` 同构。
4. **重写 `environment/validate_environment.ps1`**：断言改为「主机是 Windows 内核（`Win32NT`）」+「能创建匿名管道、置位并读回 `HANDLE_FLAG_INHERIT`」+「能创建子进程」；保留原有 isolation audit。**该文件是 F5 的锚点。**
5. **改 `environment/prepare.ps1`** 的 required 列表（去掉 `assets\*`，改为 `wspawn\*.py` + `tests\test_wspawn_basic.py`）。
6. **建镜像 + 手工 NOP/Oracle**（期望 0 / 1）；若 NOP 不是 0 或 Oracle 不是 1，先查 §5.4 那类路径问题。
7. **跑 12 个 Harbor job**（Qwen×3 + Opus×3 + Oracle×3 + NOP×3），确认 12 个 `task_checksum` 唯一且一致。
8. **组装 `jobs/` → 打包 → `windows-harbor-qc` → 上传飞书 218 槽位**（记录 `reczz28MJuh9Ygtx` 之外的那个 wlogseg 记录，需先拉表确认 record_id 与附件 token）。

---

## 6. 甲方的额外要求（215 期间确认下来的，218 同样适用）

- **`task.toml` 必须携带 `docker_image`**（与 `environment/Dockerfile` 的 `FROM` 逐字一致）。买方自检读这个字段，缺了就报 `Task has no pinned Docker image`。对应地，`skills\harbor-windows\scripts\validate_package.py` 的规则已改为「必须有且钉住 digest」。
- **`tests/required_testcases.json` 顶层必须是数组**（218/219/216 都是数组），不能包成对象。
- **`tests/` 需要 `judge.toml` + `rubric.json`**（与 `required_testcases.json` 一起构成评分链）。
- **模型门禁**：`validate_model_gate.py` 的 `REQUIRED_COUNTS` 已改为 `{"qwen":3,"opus":3}`；`validate_model_jobs.py` 的期望 job 数改为按 `REQUIRED_COUNTS` 推导（`sum+6` = 12），不再硬编码 14。门禁允许「双满分时按 `testcase_pass_sum` 破平局」，但注意：`score=1` 意味着 20/20 全过，所以**双满分时 testcase 累计必然相等，破平局救不了**——要么让 Qwen 不满分，要么让 Opus 总分更高。
- 十项人工复核需要证据包（见 `_qc_runs\wsparse-build\quality-review-filled.json` 的写法），其中 `wip94_complete` / `dynamic_d01_d20_complete` 要的是「**已逐项登记/审计**」而不是「94 项全 PASS」，所以据实填 PASS 并附产物路径即可。完整审计产物：`wip94-review.json/.md`（94 行，PASS 81 / FAIL 1 / FLAG 3 / BLOCKED 8 / N/A 1）、`dynamic-d01-d20-review.json/.md`（20 行，PASS 18 / N/A 2）。
  *已知边界*：WIP 的 **VV-14** 判 FAIL（`judge.toml` 权重和 1.0、统一分母 1.0 ⇒ 程序化占比 100% > WIP 阈值 50%），按手册需**双列**「WIP 合规 FAIL / 本题 programmatic-only 设计说明」，不得改写为 0%。

---

## 7. 本包目录说明

```
HANDOFF.md                          ← 本文件
harbor-windows/
  wfflab__wsparse-215-v1.0.0-delivery/   ← 已交付的 215（含 jobs/ 12 个）
  wfflab__wspawn-218-v1.0.0-delivery/    ← 218 半成品（无 jobs/）
  skills/harbor-windows/                  ← 门禁脚本（含我新加的 check_windows_mechanism.py 与改过的 validate_package.py）
  _reference/windows-harbor-qc/           ← 甲方质检 skill 副本（我改过 validate_model_gate.py / validate_model_jobs.py / run_delivery_qc.py / rule-matrix.md / README.md）
  _index/                                 ← 批次索引（tasks_index.csv 的 215 行已换成 wsparse）
  _qc_runs/
    wsparse-build/       ← 215 跑分现场：跑分脚本、组装脚本、QC 产物、审计产物、证据包、分数截图
    whandle-build/       ← 218 句柄继承探针（probe-handle-parent.py / probe-handle-child.py）
    wident-build/        ← 已被否定的「文件 ID」方向探针（保留作查重记录）
    windows-mechanism-rework/  ← 返修调查：飞书全量拉取、门禁自测、设计定稿、217 包对照
```

**未打进本包的东西（家里电脑需自备）**
- `models.local.json`（含明文 API key）——放回仓库根即可
- Docker 镜像与容器缓存、Harbor CLI 本体、Python/Node 运行时
- 飞书授权状态（`lark-cli auth login`）
