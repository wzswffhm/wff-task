# D01–D20 动态审计（wfflab__wlogseg-218 v1.1.0）

> 出题方只对**有原始证据**的项写结论；需要质检方独立执行的项写 `BLOCKED`。

| 项 | 内容 | 结论 | 证据 |
| --- | --- | --- | --- |
| D01 | 同身份 Golden/no-change 对照 | PASS | jobs/ 内 ctl-oracle-1..3 与 ctl-nop-1..3 |
| D02 | 逐 testcase 终态 | PASS | golden-nochange-matrix.md |
| D03 | 稳定性与干净重建 | BLOCKED | 本轮未做重复重建实验 |
| D04 | 要求实际下发 | PASS | instruction.md 全文 + task.toml |
| D05 | 需求—测试—评分双向映射 | PASS | requirement-testcase-rubric-map.md |
| D06 | 每项得分与扣分 | PASS | score-recompute.json |
| D07 | 等价实现与故障反例 | BLOCKED | 出题方只提供参考解与 no-change 端点 |
| D08 | Mock 保真 | N/A | 本题不使用任何 Mock 或替身运行时 |
| D09 | Windows 真实终态 | PASS | verifier/WINDOWS_VALUE.md + 控制组容器日志 |
| D10 | 构建与产物身份 | PASS | scope-and-identity.json 的 graded_asset_sha256 |
| D11 | 异常与日志完整性 | PASS | 每 job 无 exception_info，verifier/report.json 终态化 |
| D12 | Hack / 泄露 / 绕过 | PASS | hack-events.json + 负访问探针 |
| D13 | 独立复算 | PASS | score-recompute.json（复算与 verifier 分全一致） |
| D14 | 失败归因 | PASS | model-run-item-audit.json（无 INVALID 槽位） |
| D15 | 批次分母 | BLOCKED | 本题包不含批次层数据 |
| D16 | 交付闭环 | PASS | remediation-retest.md |
| D17 | 镜像 pin | PASS | task.toml docker_image == Dockerfile FROM |
| D18 | 身份三元组一致 | PASS | scope-and-identity.json + SEALED_MANIFEST.json |
| D19 | 提示词合规 | PASS | 轨迹为自然中文口语提问，无违禁前缀 |
| D20 | 文档与证据索引 | PASS | 本节全部产物 + 包内 REFIT / ISOLATION / WINDOWS_VALUE |
