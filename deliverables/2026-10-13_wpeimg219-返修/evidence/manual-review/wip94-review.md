# WIP 94 项对照（wfflab__wpeimg-219 v1.4.0）

> **出题方边界声明**：下列分组结论都基于本包内的可复算原始证据；WIP 手册逐条原文编号对应的**逐项动态执行**（例如 WIP 要求的独立等价实现反例、稳定性重复重建、批次分母核对）需要质检方在质检环境按手册原文执行，出题方不冒签。未执行项一律 `BLOCKED`，不写 PASS。

| 分组 | 覆盖 | 证据 | 结论 |
| --- | --- | --- | --- |
| FC | 格式与配置 | judge.toml / task.toml / adapter.toml 均可被 tomllib 完整解析；rubric 权重合计 1.0、无 llm_judge 项 | PASS |
| QD-SP | 题面与规格 | 题面 A–G 每节都有 required 覆盖（requirements 映射表） | PASS |
| QD-SO | 解法与等价实现 | 参考解通过全部 required；no-change 全 F2P FAIL | PASS |
| QD-IN | 隔离 | 三层材料清单 + 负访问探针 7 项 PASS | PASS |
| ENV | 环境 | 真实 Windows 容器；task.toml 与 Dockerfile 镜像 digest 一致 | PASS |
| VV | 验证器 | 26/27 条 required 全部终态化；无 SKIP/ERROR/NOT_RUN | PASS |

| 未由出题方执行、需质检方按手册原文完成的项 | 结论 |
| --- | --- |
| WIP 要求的独立等价实现反例（等价实现 + 删关键修复 + 硬编码 + 吞异常等） | BLOCKED（出题方只提供参考解与 no-change 两个端点） |
| WIP 要求的稳定性重复重建与干净环境复验 | BLOCKED（本轮只做了同包 3+3 控制组） |
| WIP 批次分母、历史分数混算核对 | BLOCKED（不属于本题包内容） |
