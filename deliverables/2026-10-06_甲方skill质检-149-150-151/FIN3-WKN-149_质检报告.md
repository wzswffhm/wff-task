# FIN3-WKN-149 质检报告

| 项目 | 内容 |
|---|---|
| 题目 / 批次目录 / 版本 | FIN3-WKN-149（多资产宏观压力测试）/ `work_fin-b01_20261005_fix6-149` / 1.0.6 |
| 申报难度 · 复杂度 / 判据条数 | A2 · C5 / 36 条（正分池 204，负分 2 条 −10/−7） |
| 参考解 / 三模型实测 / 均值·档位 | oracle 0.991422 / gpt 0.615196 · opus 0.273284 · qwen 0.898284 / 0.595588 · **A2**（余量 10.4pp） |
| 质检方式 / 日期 | 甲方 weakness-qc 流程：机器门禁 + 判分复算 + 独立重算抽查 + 结构与安全检查 / 2026-10-06 |
| **质检结论** | **通过**：0 项必须整改；4 项提示（均不构成退回理由） |

## 一、结论
可以交付。机器门禁全绿、判分逐条可复算且与现行判据零漂移、难度证据有效（非口径歧义撑着）、结构与打包合规。无必须整改项。

## 二、必须整改
（无）

## 三、提示（不影响验收，均不构成退回理由）
1. **check_rubric_style --strict 报 3 条量词**（R24/R29/N02 含「个别/多数」）：经回规范原文复核，量词均出现在 **likert 中间档位的阶梯锚点**（如 N02「5=绝大多数→4=超过半数→3=约半数→2=仅个别」），属递进量化定义而非无定义量词；得分线锚点（5=/1=）精确。不构成退回理由；改 description 需重跑判官，代价大于收益。
2. **R29/R33 标 Subjective**（脚本 NOTE）：两条为论证质量/专业判断类 likert 条目，人工确认保留 Subjective 合理。不构成退回理由。
3. **trial.log 含本机路径 `/home/wff`**（4 个执行体各 1 处）：harbor 运行日志自带，具取证价值（证明试次真实性），按案例 5 处置判提示；如需可移入 `轨迹/` 并脱敏。无密钥、无内网域名。不构成退回理由。
4. **oracle 无 claude-code 轨迹**：oracle 为 harbor 内置 agent 执行 solve.sh，不产生 claude-code 轨迹；包内 `轨迹/说明.txt` 已如实注明并保留 oracle.txt/trial.log。设计使然。不构成退回理由。

## 四、已核实通过项
### 门禁与结构
| 门禁 | 结果 |
|---|---|
| validate_task_package | PASS（内容质量正分占比 91%，+10 ×2） |
| validate_rubrics | PASS（json↔toml 条数/negate 集合/正分池 204/likert 双标度/锚点一致） |
| check_complexity（先 --self-test PASS） | PASS：文件数 39→C4，产物 7→仅 C5，声明 C5 合法（产物区间并集） |
| check_cross_model_concentration | **9.3% < 25%**：全体一致 0 分仅 5 条（R17/R05/R06/R07/R27，合计 19 分），oracle 对这 5 条全为 1（金标可达，非金标缺陷） |
| check_package_permissions（批次包） | PASS：solve.sh/test.sh 0755+LF、golden 双份逐字节一致、无残留、含交付文档与跑分产物 |
| check_batch_quota | 单题包进度提示，非阻塞；`category=weakness` 为生产规范规定取值 |
| 密钥/内网扫描 | 无 sk-/Bearer/api_key/内网域名命中 |
| 执行体目录白名单 | 合规（output/reward*.json/轨迹） |

### 判分与算术
- **判分自洽**：4 个执行体按 rewardkit 公式 `Score=(Σ正 w·v − Σnegate w·(1−v))/Σ正w` 复算，与 reward.json **逐一致**（0.991422/0.615196/0.273284/0.898284）；reward-details 的 description/weight 与现行 tests/rubrics.toml **36 条零漂移**。
- **轨迹框架**：三模型均 `agent=claude-code`、`version=2.1.114`、含 steps、claude-code.txt 在位可解析。
- **独立重算**（不引用金标）：① 金标 S3 表 27 个月、首月 **2018-02**（必修#1 闭环实测）；② oracle R16=1、零分判据空集；③ 三模型共同全零 = R05/R06/R07/R17/R27 共 5 条，与交付文档声明一致。
- **难度**：参考解 0.991422 ≥0.85；均值 0.595588 <0.7 落 A2；qwen 0.898 非零（非死题）；单模型 >0.7 不受约束。

## 五、重跑影响说明
本轮未改动任何判据/权重/金标/题面，无需任何重跑。

## 六、质检边界
- 未覆盖：金标排版观感、参考答案专业正确性的人检、trigger 能否稳定诱发 W 标签弱点的行为学验证（需人检）。
- `check_instruction_anchors.py` 硬编码甲方自有批次锚点（FIN-127/128/129-W），对本题不适用 → 判据锚点核对以本报告人工复核 + 前轮质检整改记录为准。
- task.zip / answer.zip 拆分包不适用 check_package_permissions 的批次包结构校验（脚本按批次包口径报 FAIL，属口径不符非缺陷；task 包五件套齐全、answer 包 22 项 golden 均实测在位）。
