# 215 / 216 返修实施与验证报告（2026-10-16）

对象：飞书记录 `reczz28KwEOO3xHy`（215 wsparse，甲方ID 12）、`reczz28KQU8reW2k`（216 wvas，甲方ID 11）。
本报告只覆盖飞书返修原因里点名的条目，不涉及清单 v3（那 9 个包与本次无关）。

## 一、逐条修复

| 返修条目 | 问题 | 本次改动 | 验证 |
|---|---|---|---|
| **216-1** | 包里的 Task 校验值和 12 份原始运行记录对不上 | 把 `REFIT-2026-10-14.md`、`verifier/WINDOWS_VALUE.md` 放回题包（它们是身份计算的一部分） | 放回后 `harbor_dirhash` 立刻回到 `253161fb10921f97…`，与 12 份 job 记录逐条一致；其余 259 个文件与 git 历史逐字节相同 |
| **215-1 / 216-2** | 候选模块与隐藏测试在同一 pytest 进程，权限与评分端未分离 | `tests/run_tests.ps1` 增加：① 运行期对评分目录与隐藏套件源目录设置 **deny-write ACL**（`icacls /deny`），跑完恢复；② 每个 case 的结果经 **conftest 钩子镜像到 pytest 真实 stdout**（带一次性 nonce），评分端只读这条受信通道；③ 与候选可写的 json report **交叉校验**，两者不一致即判 INVALID；④ 受限窗口内主动尝试写评分目录 / 套件源目录，**必须被拒绝**（反例） | 两包实测 `isolation.enforced=true`，两个探针写入均被拒；受信通道收到的 case 数与套件一致（215=20，216=16） |
| **215-2 / 216-3** | 基础设施故障被当成普通失败（依赖缺失、setup 报错仍输出 VALID/0） | `run_tests.ps1`：先做**不 import 候选**的 harness 自检（pytest + json-report 可用性）；`collected=0` 一律 INVALID（删掉旧的“收集不到即候选 FAIL”分支）；216 的 outcome 映射把 `error/skip` 之类判为 INVALID。`aggregate_results.ps1`：INVALID 时 `formal_score`、`verdict`、`test.report.score` **留空**，`test.report.status` 如实写 `INVALID`，退出码 2 | 见下表“基础设施故障”对照 |
| **215-3** | `regions`/`allocated_ranges` 未与独立实测比较（实测 8192、候选报 8193 仍 PASS） | 隐藏套件新增 `_cluster_spans()`，把候选区间与**套件自己用 `FSCTL_QUERY_ALLOCATED_RANGES` 量到的区间**按簇归一化后逐区间比较；`test_allocated_ranges_are_the_real_extents` 与 `test_written_extent_is_the_only_allocation` 都加总量容差 + 区间集合相等 | 见下表“错误实现 8193”对照 |
| **216-4** | `file_backed_regions` 只校验“返回项属于 regions”，`[]` 也能 PASS，违反题面 B.4 | 断言改为：`regions` 中所有 `path is not None` 的项必须**全部**出现在 `file_backed_regions`，且顺序一致；同时把该 case 由 P2P 重新归类为 **F2P**（旧断言下 NOP 也能过，加强后 NOP 必然失败，符合“F2P = 空跑基线失败”的定义） | NOP 下 F2P 9/9 失败、P2P 0/7 失败；参考实现 16/16 通过 |
| **215-4 / 216-5** | 缺作者写测试前的用例设计与可核验的造测可见会话 | **尚未解决**，见第四节 | — |

同步动作：隐藏套件在 `tests/` 与 `verifier/tests/` 的两份副本保持逐字节一致（215 `a51e434b…`，216 `bfe41f7d…`），并同步更新了 `verifier/README.md`、216 的 `verifier/SEALED_MANIFEST.json`、`REFIT-2026-10-14.md` 里记录的哈希；216 的 P2P→F2P 重分类同步改了 `required_testcases.json`、`rubric.json`、`judge.toml`、`verifier/rubric.conditions.json`（`check_required_vs_rubric.py`：集合与分组一致）。

## 二、本地实测对照（Windows 物理机，PowerShell 5.1 + Python 3.12 + pytest 8.3.5）

### 1. 基础设施故障 → INVALID（修复前 vs 修复后）

| 场景 | 链路 | run 退出码 | run_validity | formal_score | report.status | report.score |
|---|---|---|---|---|---|---|
| 215：套件一个 case 都收集不到 | 修复前 | 1 | VALID | **0** | VALID | 0 |
| 215：同上 | 修复后 | 2 | **INVALID** | **null** | **INVALID** | **null** |
| 216：独立 fixture 在 setup 阶段报错 | 修复前 | 1 | VALID | **0** | VALID | 0 |
| 216：同上 | 修复后 | 2 | **INVALID** | **null** | **INVALID** | **null** |

### 2. 断言强度（215，错误实现 = 参考实现 + 每个分配区间多报 1 字节）

| 套件版本 | 候选实现 | `allocated-ranges-are-the-real-extents` |
|---|---|---|
| 修复前（git 1568cfb3） | 区间长度 +1（实测 8192 → 报 8193） | **PASS**（漏判） |
| 修复后 | 同上 | **FAIL**（判住） |
| 修复后 | 参考实现 | PASS（无误杀） |

### 3. 控制组与门禁（修复后）

| 包 | 参考实现 | 缺陷实现（NOP） |
|---|---|---|
| 215 | 20/20 PASS，VALID/1，exit 0 | 10 FAIL / 10 PASS，VALID/0，exit 1，失败项**全部是 F2P**（P2P 零失败） |
| 216 | 16/16 PASS，VALID/1，exit 0 | 9 FAIL / 7 PASS，VALID/0，exit 1，P2P 零失败，F2P 9/9 失败 |

### 4. 隔离强制

两包每次运行都记录 `isolation.enforced=true`、`restricted=[评分目录, <pkg>\tests, <pkg>\verifier\tests]`、两个写入探针 `denied=true`、`trusted_cases` 与套件用例数相等。`REFIT`/`README` 说明的两份副本哈希一致。

## 三、改动文件清单

215：
- `tests/run_tests.ps1`（隔离 + 受信通道 + INVALID 语义 + 自检）
- `tests/aggregate_results.ps1`（INVALID 时分数留空）
- `tests/test_wsparse_semantics.py`、`verifier/tests/test_wsparse_semantics.py`（簇级区间比对）
- `verifier/README.md`（记录新的套件哈希）

216：
- 上述同名的 6 个文件
- `REFIT-2026-10-14.md`、`verifier/WINDOWS_VALUE.md`（放回，恢复身份）
- `tests/required_testcases.json`、`tests/rubric.json`、`tests/judge.toml`、`verifier/rubric.conditions.json`（P2P → F2P 重分类）
- `verifier/SEALED_MANIFEST.json`（套件哈希与大小）

## 四、未解决项：作者造测证据（215-4 / 216-5）

甲方要的是**作者实际造测会话**与首次写测试的时间线，并明确“不能用当前质检会话”“不能事后补写成旧记录”。

本次穷尽扫描了本机 DSH 会话存档：

- 位置：`%USERPROFILE%\.dsh\sessions\`，共 5 个工作目录、30 个会话文件（42.9 MB 压缩）。
- 方法：解压每个会话（zstd），逐事件检索隐藏套件文件名、`write_file`/`edit_file`/`apply_patch` 类写入事件，以及造题特征词（`FSCTL_SET_SPARSE`、`VirtualQueryEx`、`preallocate`、`MEMORY_BASIC_INFORMATION`、`required_testcases.json`、`judge.toml`、`instruction.md`、`windows_mechanism.json`）。
- 结论：**没有任何会话包含写入 `tests/test_wsparse_semantics.py` 或 `tests/test_wvas_semantics.py` 的事件**。命中的会话全部是造题之后的审查/替换/交付会话（当前会话自身也因此命中）。也就是说，这两个题包的造题过程没有留在本机会话存档里。

因此这一项无法用“原始造测会话”直接闭合。可选做法见汇报里的选项（用户提供原件 / 用现有构建痕迹整理并如实标注 / 说明无法提供）。

## 五、验证产物索引

- `harbor-windows/_qc_runs/wsparse215-fix/`：215 的 oracle/错误实现工作区、旧套件与旧 harness 副本、各轮 run.log、checks.json、result.json
- `harbor-windows/_qc_runs/wvas216-fix/`：216 的同类产物，外加 `error-verifier/`（setup 报错探针套件）
- `harbor-windows/_qc_runs/wip94-evidence-20261016/`：会话存档扫描脚本与结果
- `harbor-windows/_qc_runs/wsparse215-fix/venv/`：本次验证用的 Python 环境（pytest 8.3.5 + json-report，取自题包 vendor wheels）
