# 判分侧材料（wfflab__wpeimg-219）

本目录**不是 Agent 题包的一部分**，也不会被 `environment/Dockerfile` 打进
候选镜像。评测侧在判分阶段把它注入到容器内独立路径：

| 本目录 | 容器内注入点 | 用途 |
| --- | --- | --- |
| `tests/test_wpeimg_semantics.py` | `C:\verifier\wfflab__wpeimg-219\tests\` | 隐藏行为断言（pytest） |
| `rubric.conditions.json` | `C:\verifier\wfflab__wpeimg-219\` | 每条 rubric 的判据与失败归因 |

Agent 可见面只有 `environment/workspace/`（容器内为 `C:\testbed`）：隐藏断言与
参考解都只存在于判分侧，Agent 容器内不存在。

## 注入约定

判分脚本 `tests/run_tests.ps1` 按下列顺序解析隐藏断言根目录，命中即用：

1. `run_tests.ps1 -VerifierRoot <dir>`；
2. 环境变量 `WPEIMG_VERIFIER_ROOT`；
3. `<任务根>\tests`（题包内自带）；
4. `<任务根>\tests\verifier`（题包内自带）；
5. `C:\verifier\wfflab__wpeimg-219`；
6. `C:\verifier`；
7. 包内平级目录 `<包根>\outside_harbor-verifier\wfflab__wpeimg-219`（本地复现用）。

参考实现按 `solution/solve.ps1` 的解析顺序注入（`C:\solution\reference\wpeimg`
优先）。解析不到隐藏套件时判分入口以退出码 2 报 INVALID，不会退化成 0 分。

## 隐藏套件构成的判分面

27 条用例，19 条 FAIL_TO_PASS、8 条 PASS_TO_PASS；分组与权重见
`rubric.conditions.json` 与 `../rubric.json`。

`checksum-matches-authoritative-values`、`checksum-ignores-the-stored-field`、
`accumulator-matches-authoritative-values` 里的期望值是
`imagehlp!MapFileAndCheckSumW` 在 Windows 上离线取得的常量，套件本身不依赖
容器内的任何 Windows 组件即可运行；它们同时锁住了「实现不得调用系统库代算
校验和」这一约束（由 `p2p-package-has-no-external-dependencies` 做源码审计）。
