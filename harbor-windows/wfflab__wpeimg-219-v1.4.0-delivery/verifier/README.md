# 判分侧材料（wfflab__wpeimg-219，task version 1.4.0）

本目录**不是 Agent 题包的一部分**，也不会被 `environment/Dockerfile` 打进
候选镜像。评测侧在判分阶段把它注入到容器内独立路径：

| 本目录 | 容器内注入点 | 用途 |
| --- | --- | --- |
| `tests/test_wpeimg_semantics.py` | `C:\verifier\wfflab__wpeimg-219\tests\` | 隐藏行为断言（pytest） |
| `rubric.conditions.json` | `C:\verifier\wfflab__wpeimg-219\` | 每条 rubric 的判据与失败归因 |
| `oracle/reference/wpeimg/` | `C:\solution\reference\wpeimg\` | Golden / Oracle 参考实现 |
| `oracle/solve.ps1`、`oracle/solve.bat` | `C:\solution\` | Oracle 安装入口 |
| `oracle/README-original.md`、`README.md` | 不注入 | 参考实现的权威行为与错误分类判据（审计用） |
| `WINDOWS_VALUE.md` | 不注入 | Windows 价值逐条映射与采购分类（质检 ZQ00x-03） |
| `ISOLATION.md` | 不注入 | 公开开发测试 / 隐藏验收 / 参考解的分层与适配口径（质检 ZQ00x-06） |
| `negative_access_probe.ps1` | 不注入 | 负访问只读探针，产出可归档的隔离证据 |
| `evidence/` | 不注入 | 权威校验和的取得过程（Windows `imagehlp!MapFileAndCheckSumW`） |
| `SEALED_MANIFEST.json` | 不注入 | 本目录全部文件的 sha256 / size 清单 |

Agent 可见面只有 `environment/workspace/`（容器内为 `C:\testbed`）：隐藏断言与
参考解都只存在于判分侧，Agent 容器内不存在。

> **v1.0.0 → v1.1.0 的隔离整改**：v1.0.0 把隐藏套件放了**两份**
> （`tests/test_wpeimg_semantics.py` 与 `tests/verifier/tests/`），且解析顺序按路径
> 拼接命中包内 `tests/`，把候选工作区放在可解析路径上；v1.1.0 删除 legacy 重复副本、
> 把 `C:\tests` 作为**平台投放的只读通道显式声明**，解析顺序里彻底移除候选工作区与
> 任务根，并补齐判分侧正本的 sha256 对账与负访问探针。

## 注入约定

判分脚本 `tests/run_tests.ps1` 按下列顺序解析隐藏断言根目录，命中即用：

1. `run_tests.ps1 -VerifierRoot <dir>`；
2. 环境变量 `WPEIMG_VERIFIER_ROOT`；
3. `C:\verifier\wfflab__wpeimg-219`；
4. `C:\verifier`；
5. `C:\tests`（Harbor 在跑 `tests/test.ps1` 之前把包根 `tests/` 复制到此，
   这是平台唯一的套件投放通道）；
6. 包内平级目录 `<包根>\outside_harbor-verifier\wfflab__wpeimg-219`（本地复现用，
   不进容器）。

列表中**不含**候选工作区（`C:\testbed`、`environment\workspace`）与任务根
`<任务根>\tests`：候选永远不能提供判分断言。`tests/` 在候选容器内是只读的
（`agent_visible_paths.json` 与 `adapter.toml` 双重声明）。

参考实现按 `solution/solve.ps1` 的解析顺序注入（`C:\solution\reference\wpeimg`
优先）。两处都解析不到时判分入口以退出码 2 报 INVALID，不会退化成 0 分。

## 版本与评分口径

- `task_version = 1.4.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、
  `llm_judge_weight = 0.0`（1.0.0 曾声明 0.5 的评审权重但从未采集分，已废止，
  见包根 `REFIT-2026-10-13.md`）。
- required testcase 共 **43** 条：F2P 35 条 / P2P 8 条；全过为 1，否则为 0，
  required 缺失或未终态一律 INVALID。
  > 43 条超出甲方「5–27 条正常」的上界，按甲方口径属于**提示人工复核**而非失败；
  > 扩大颗粒度有两个动机：拉开主模型区分度（1.2.0 → 1.3.0）与把判据锚到真实的
  > Windows 系统服务（1.3.0 → 1.4.0），见 `REFIT-2026-10-13.md` §R8–§R10。
- 1.0.0 曾在 rubric 里列出 `p2p-error-kind-is-validated`，而套件从未产出该
  check id（恒判 FAIL）；1.1.0 已删除该条目。
- 1.2.0 新增两个程序化评分组：`data-directories`（0.08，4 条）与
  `authenticode-detection`（0.06，3 条），对应题面新增的 A2 节。
- 1.3.0 新增 `signature-decoding`（0.05，5 条），对应题面新增的 F2 节：
  `signature_info()` 必须自行走 PKCS#7 `SignedData` 的 DER，报出 contentType OID、
  digestAlgorithms、证书条数与签名者条数，并对 `dwLength` 与文件不符的记录抛
  `WImgError(kind="structure")`。判据锚定在真实签名字节上（`offset=13824`、
  `size=13304`、`revision=0x0200`、`certificate_count=4`、`signer_count=1`）。
  实测依据：1.2.0 时 Qwen 三轮 34/34 全满、Opus 2/3，区分度不成立；1.3.0 加入
  该组后 Qwen 三轮均 37/39（第一轮正是栽在签名解析），Opus 三轮 39/39。
- 1.4.0 新增 `windows-live-services`（0.12，4 条），对应题面新增的 F3 节：
  **判分过程本身在 Windows 上调用系统组件**——`imagehlp!MapFileAndCheckSumW`
  对判分时现场构造的映像变体给出权威校验和；`kernel32!CreateFileW` 提供真实
  文件句柄驱动 `iter_sections()`。封装在 `verifier/tests/win_services.py`，与隐藏
  套件一起投放到 `C:\tests`，候选工作区不含它。被测实现仍不得导入
  `ctypes`/`subprocess`，两条要求相互独立。
