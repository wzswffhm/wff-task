# 多资产稳健配置专户：三季度宏观压力测试与调仓建议

## 业务场景与角色

你是某资产管理机构的**多资产风险经理**。风险委员会将于 2026 年 9 月下旬召开三季度例会，要求你对「多资产稳健配置专户」做一次宏观压力测试，并对投资经理、风险管理部和宏观策略组分别提出的调仓方案给出意见。

你的结论会写入委员会决议，并直接决定投资经理下一周的调仓指令。**分析截至日为 2026-09-15。**

## 专户基本情况

专户净值 **1 亿元**（10,000 万元）。当前持有沪深300、中证500、创业板三只指数基金，合计占总资产 50%；中长期国债组合占 20%；美元现金及存款占 10%；不对冲汇率的标普500 QDII 基金占 10%；人民币现金及货币基金占 10%。

## 可用源文件

全部输入材料位于 `/app/input_files/`（**只读**）。请以该目录中的文件为准，不要使用任何外部数据。

### 一、市场与宏观数据快照（27 个 CSV）

| 文件 | 内容 |
|---|---|
| `snapshot_000300SH_seg1.csv` / `_seg2.csv` | 沪深300 指数日行情：`date, open, high, low, close, pre_close, amount` |
| `snapshot_000905SH_seg1.csv` / `_seg2.csv` | 中证500 指数日行情，字段同上 |
| `snapshot_399006SZ_seg1.csv` / `_seg2.csv` | 创业板指数日行情，字段同上 |
| `snapshot_cgb_yield_1y.csv` | 中债国债收益率曲线 1 年期：`date, yield_pct`（百分数） |
| `snapshot_cgb_yield_2y.csv` | 同上，2 年期 |
| `snapshot_cgb_yield_5y.csv` | 同上，5 年期 |
| `snapshot_cgb_yield_10y.csv` | 同上，10 年期 |
| `snapshot_cgb_yield_30y.csv` | 同上，30 年期 |
| `snapshot_usdcnh_seg1.csv` / `_seg2.csv` | USD/CNH 汇率：`date, usdcnh` |
| `snapshot_spx.csv` | 标普500 指数（美元计）：`date, close` |
| `snapshot_shibor_seg1.csv` / `_seg2.csv` | Shibor：`date, shibor_on, shibor_1w`（百分数） |
| `snapshot_lpr_1y.csv` | 1 年期 LPR：`date, lpr_1y`（百分数） |
| `snapshot_lpr_5y.csv` | 5 年期 LPR：`date, lpr_5y`（百分数） |
| `snapshot_pmi_manufacturing.csv` | 制造业 PMI：`date, pmi_mfg` |
| `snapshot_afre_stock.csv` | 社会融资规模存量：`date, afre_stock`（万亿元） |
| `snapshot_dr007.csv` | 银行间 7 天期资金利率 DR007：`date, dr007`（百分数） |
| `snapshot_ppi_yoy.csv` | PPI 当月同比：`date, ppi_yoy`（百分数） |
| `snapshot_ust_10y.csv` | 美国 10 年期国债收益率：`date, yield_pct`（百分数） |
| `snapshot_ust_m2.csv` | 美国国债 m2 期限收益率：`date, yield_pct` |
| `snapshot_ust_m4.csv` | 美国国债 m4 期限收益率：`date, yield_pct` |
| `snapshot_trade_calendar.csv` | 上交所交易日历：`date, exchange, is_trading_day` |
| `snapshot_data_manifest.csv` | 数据清单：`file, records, start, end, possible_truncation, source` |

> 数据口径提示：各文件按不同批次导出，**分段文件名相同前缀的表示同一序列的两个导出批次**；`snapshot_data_manifest.csv` 中的 `possible_truncation` 字段为上游系统自动生成，**不保证与文件实际内容一致**，请以文件实际内容为准。

### 二、参数、方案与规则

| 文件 | 内容 |
|---|---|
| `params_holdings.csv` | 当前持仓与推荐权重：`asset, asset_class, weight_current, weight_recommended` |
| `params_positions.csv` | 当前持仓明细（含金额，单位万元） |
| `params_limits.csv` | 九项限额参数：`id, constraint, op, lower, upper, unit, note` |
| `params_duration.csv` | 中长期国债组合关键期限久期贡献：`tenor, duration_contribution` |
| `params_committee_shocks.csv` | 委员会沿用的四个情景冲击参数（含各期限国债 bp 冲击） |
| `plans_candidates.csv` | 三个候选方案权重：`plan_id, proposer, w_000300, w_000905, w_399006, w_cgb, w_usd_cash, w_spx_qdii, w_cny_cash` |
| `rules_scenarios.csv` | 四个情景的月度识别规则：`scenario_id, scenario, rule, tag, shock_type` |
| `rules_windows.csv` | 历史窗口构造规则：窗口起点、长度与选取方式 |
| `rules_checks.csv` | 九项约束检查规则：`check_id, limit_id, description` |
| `rules_rebalance.csv` | 调仓执行规则：执行顺序、现金下限、QDII 结算、换手率口径等 |

### 三、输出模板

| 文件 | 说明 |
|---|---|
| `template_memo.md` | 风险委员会决策备忘录模板，含**八个章节**的骨架与填写要求 |
| `template_monitor.csv` | 八个监测指标的表格模板（阈值、最新值、状态、是否触发） |

## 交付物要求

全部交付物写入 `/app/output/`，共 **7 项，全部为必交**：

| 文件名 | 说明 |
|---|---|
| `FIN3-WKN-149_风险委员会决策备忘录.md` | 主交付物。按 `template_memo.md` 的**八个章节**逐章填写，Markdown 格式 |
| `FIN3-WKN-149_reproduce.py` | 可复算代码。从 `/app/input_files/` 原始快照读入，**不得硬编码任何结论数值**，运行后应能复现备忘录中的全部数字与图表 |
| `FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png` | 数据核验图：各序列实际覆盖区间、缺口与分析截至日 |
| `FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png` | 历史风险复合图：**a 各方案累计净值曲线**；**b 各方案年化波动率、1 日 ES99、10 日 VaR99、最大回撤与限额参考线** |
| `FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png` | 情景识别与校准复合图：**a 四情景月度识别结果**；**b 各情景历史窗口校准冲击**；**c 沿用冲击与历史校准冲击的严格程度对比** |
| `FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png` | 方案决策与执行复合图：**a 各方案最大压力损失，须同时画出 8% 压力损失上限线与 7% 缓冲线**；**b 调仓执行现金路径与 8% 下限线**；**c 反向压力测试最可能情景** |
| `FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png` | 监测触发图：八个监测指标最新值与阈值 |

图表要求：**全部为 PNG，中文标注**，涉及限额的图必须画出限额参考线；**同一 PNG 内的多个子图须以 `a`/`b`/`c` 分面标题区分**（如 `图2-a`、`图2-b`），每张图在备忘录对应章节中配一句说明并嵌入。

## 硬约束

1. **数据核验必须做在计算之前**。样本区间的起止与交易日数量、各序列的实际覆盖区间与缺口、逐条数据异常、结构性空值的处理方式，都必须在备忘录第二章中显式说明；不得把任何空值按 0 参与计算。
2. **价格对齐口径**：所有跨市场序列在计算收益前，必须先对齐到上交所估值日；不同市场交易日不一致时按前向填充处理，但结构性空值不参与填充。
3. **国债组合的收益必须按关键期限久期折算**，不得直接用收益率差值的简单加总；**标普500 的人民币计收益必须按复合方式折算**，不得使用加法近似。
4. **组合日收益按方案权重每日再平衡**计算。
5. **压力测试必须完整**：4 个方案 × 4 个情景 × 2 套冲击的全部结果都要给出，每个结果须拆分为境内权益、标普500（人民币计）、美元现金、国债四部分贡献，四部分之和必须等于组合损益。
6. **九项约束必须逐条检查**，对每个方案给出通过/未通过与超限幅度；外币资产敞口的构成须按 `params_limits.csv` 中的口径说明判定。
7. **推荐方案必须给出构造依据与其唯一性说明**，并给出交易清单与执行顺序。
8. 金额单位统一为**万元**，百分比保留**两位小数**，收益率变动注明单位（bp 或 %）。
9. 交付物文件名**必须与上表逐字一致**（大小写、下划线、连字符均不得改动），不得添加日期、版本号等动态成分。
10. 不得修改 `/app/input_files/` 中的任何文件。
