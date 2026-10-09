# Reddit, Inc. IPO Pricing Committee 备忘录

**日期：** 2024-03-20　**建议：Proceed at $34.00**

## 结论

现行控制口径为 `Committee_Policy_v3_20240320.xlsx`。v2 关于保留 SBC 加回、3.5x–5.5x peer 区间、10% 折扣及按全部发行股份计费的条款均已失效。按 v3，支持价格为 **$31.27–$37.25**，midpoint **$34.26**；拟议价 $34.00 位于区间内，较 midpoint 低 **$0.26/share**，不超过 CP-14 的 $0.50 门槛。结构性错误已在本模型修复，建议 Proceed。该价格、22% 增长、倍数、折扣及 cap-table snapshot 均为内部假设，不是 SEC 已实现结果。

## 盈利质量与估值

SEC-01 的 2023A Revenue 为 **$804.029mm**、净亏损 **$-90.824mm**、管理层 Adjusted EBITDA **$-69.275mm**。按 CP-03 撤回持续性 SBC **$49.086mm** 后，承销口径 EBITDA 为 **$-118.361mm**；重组费 **$8.098mm** 已在管理层口径调整，不重复加回。FCF **$-84.838mm**，两项均为负，是主要 QoE 风险。故采用 EV/2024E Revenue：$804.029×(1+22%)=**$980.915mm**。净现金桥计入现金 $401.176 与有价证券 $811.946，合计 **$1,213.122mm**；4.0x/4.5x/5.0x 后统一折价 12.5%。

## 发行结构与稀释

Base 为 primary **15.276527mm**、secondary **6.723473mm**；secondary 不形成公司募集资金或新增股数。$34.00 下公司 gross/net primary proceeds 为 **$519.402mm / $486.432mm**；承销费仅按 primary gross 的 5.0% 计提，固定费用 $7.000mm 仅一次。Base post-money 股数 **158.993090mm**，新增占比 **9.61%**。3.300000mm greenshoe 单列 full-exercise：net proceeds **$593.022mm**，post-money **162.293090mm**，新增占比 **11.45%**。SEC-02 在假定 $32.50 下的 NTBV/share $11.17、即时稀释 $21.33 可交叉验算，但不得外推为 $34 口径。

## 数据核验

- `financials/monthly_revenue_2022_2023.csv:14`：2022-08 与第 9 行同月、同源、同值重复；原始 FY2022 合计超过 SEC 年度数。 依据：完全重复记录去重；SEC-01 年度收入为控制数。 处置：排除第 14 行 57.100；去重后 FY2022=666.701。
- `financials/monthly_revenue_2022_2023.csv:26, financials/monthly_revenue_2022_2023.csv:27`：2023-12 同月存在 68.979(SEC-01) / 66.500(INT-01)。 依据：CP-02 按 Source_Index Priority 升序取值；委员会邮件明确排除 IR preliminary 残留。 处置：采用 68.979(SEC-01)；排除 66.500(INT-01)；FY2023=804.029。
- `financials/revenue_by_segment_2022_2023.csv:5`：FY2023 Other=152.470，与 SEC-01 的 15.247 不符；分部合计不等于年度收入。 依据：SEC-01 审计年度数及分部披露优先于待复核明细。 处置：采用 SEC-01 Other=15.247；分部合计=804.029。
- `financials/sbc_detail_2022_2023.csv:10`：TOTAL=49.680，四项组成合计及 SEC-01 均为 49.086。 依据：组成项交叉加总并与 SEC-01 年度数勾稽。 处置：TOTAL 改按 49.086 使用，且总计行不与组成项再次相加。
- `financials/restructuring_detail_2023.csv:5`：TOTAL=8.098 与组成项并列；全行求和会错误得到 16.196。 依据：TOTAL 为小计；组成项合计与 SEC-01 年度数一致。 处置：采用 TOTAL=8.098，不重复汇总；CP-04 下不二次调整 EBITDA。
- `financials/fcf_bridge_2023.csv:4`：FCF=-84.838 是前两行计算结果；全行求和会错误得到 -169.676。 依据：SEC-01 定义 FCF=经营现金流-资本开支；资本开支在底表以负数列示。 处置：按 -52.026+(-32.812)=-84.838，结果行不再加总。

## 处置与边界

SEC 历史数优先于 INT-01 flash；bank comps 与研究资料仅作交叉验证。主 `Source_Index.csv` 未登记委员会文件使用的 `UW-01`，未虚构来源编号，已在追溯表标注“待核实”；不影响数值，但正式归档前应补齐索引治理。未使用 2024-03-20 后信息、最终发行结果或上市后表现。
