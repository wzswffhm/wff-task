# Golden 入口（参考解不随本题包交付）

本目录只保留 Golden / Oracle 控制跑所需的入口脚本，**不含参考答案**：
参考实现本体（`reference/`）、补丁（`oracle.patch`）与判据明细均已移出
Agent 可见题包，改由评测侧在判分阶段注入到独立目录。

## 目录内容

| 文件 | 作用 |
| --- | --- |
| `solve.ps1` | 定位并安装判分侧注入的参考实现到候选工作区 |
| `solve.bat` | 标准 Harbor 的 `.bat` 入口，委托 `solve.ps1` |

## 参考实现的查找顺序

`solve.ps1` 按以下顺序查找参考实现目录（命中即用）：

1. `-ReferenceRoot <dir>` 参数；
2. 环境变量 `WFMT_REFERENCE_ROOT`；
3. `C:\solution\reference\wfmt`（评测平台注入点）；
4. `<包根>\outside_harbor-verifier\wfflab__wfmt-215\oracle\reference\wfmt`
   —— 与 Agent 可见题包**平级**的判分侧目录，仅在本地复现时使用。

找不到参考实现时脚本以退出码 1 结束，不会退化成"跳过 Oracle"。
