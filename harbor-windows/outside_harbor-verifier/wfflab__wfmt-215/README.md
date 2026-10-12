# 判分侧材料（wfflab__wfmt-215）

本目录**不是 Agent 题包的一部分**，也不会被 `environment/Dockerfile` 打进
候选镜像。评测侧在判分阶段把它注入到容器内独立路径：

| 本目录 | 容器内注入点 | 用途 |
| --- | --- | --- |
| `tests/test_wfmt_semantics.py` | `C:\verifier\wfflab__wfmt-215\tests\` | 隐藏行为断言（pytest） |
| `rubric.conditions.json` | `C:\verifier\wfflab__wfmt-215\` | 每条 rubric 的判据与失败归因 |
| `oracle/reference/wfmt/` | `C:\solution\reference\wfmt\` | Golden / Oracle 参考实现 |
| `oracle/solve.ps1`、`oracle/solve.bat` | `C:\solution\` | Oracle 安装入口 |
| `oracle/oracle.patch` | `C:\solution\` | 参考补丁（仅审计留档） |
| `evidence/verifier-run/` | 不注入 | 上一轮 Oracle 运行的判分产物留档 |

Agent 可见面只有 `outside_harbor-assets/wfflab__wfmt-215/`，其 `environment/workspace`
之外的目录（`tests/` 的断言、`solution/` 的参考解）在本目录中，Agent 容器内不存在。

## 注入约定

判分脚本按下列顺序解析隐藏断言根目录，命中即用：

1. `run_tests.ps1 -VerifierRoot <dir>`；
2. 环境变量 `WFMT_VERIFIER_ROOT`；
3. `C:\verifier\wfflab__wfmt-215`；
4. `C:\verifier`；
5. 包内平级目录 `<包根>\outside_harbor-verifier\wfflab__wfmt-215`（本地复现用）。

参考实现按 `solution/solve.ps1` 的解析顺序注入（`C:\solution\reference\wfmt`
优先）。两处都解析不到时判分入口以退出码 2 报 INVALID，不会退化成 0 分。
