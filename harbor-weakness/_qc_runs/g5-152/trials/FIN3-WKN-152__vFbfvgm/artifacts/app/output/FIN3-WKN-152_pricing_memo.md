# Pricing Committee 备忘录 | Reddit, Inc. IPO 发行前复核(FIN3-WKN-152)

**复核时点 / 信息截止**:2024-03-20(正式定价前)。**信息集纪律**:仅使用截止前 SEC-01~04 公开事实(S-1/A,as-of 3/11、3/15)与 UW-01 内部委员会假设;最终定价、发行后文件、上市后表现一律不进入 Base。拟议 $34 为内部决策输入(UW-01),非已实现结果;22% 增长、4.0–5.0x 倍数、12.5% discount、pre-money 股数 143.7166m 与 cap-table snapshot 均属内部假设,不得表述为 SEC 公开事实。单位:USD mm、USD/share。

## 一、结论:Proceed @ $34.00

| 处置测试(Committee_Policy) | 结果 | 判定 |
|---|---|---|
| 位于支持区间 [$31.27, $37.25] | $34.00 | PASS |
| 距 midpoint $34.26 不超过 $0.50 | $0.26 | PASS |
| 发行结构无未解决 hard error | 10 条 legacy 错误全部修正 | PASS |

## 二、支持价格区间(EV / 2024E Revenue)

承销口径 2023A EBITDA = **-118.4**(管理口径 -69.3 撤销 SBC 加回 49.1)仍为负,按 Policy 以 2024E Revenue 为主估值分母。

| 步骤 | Low 4.0x | Mid 4.5x | High 5.0x |
|---|---|---|---|
| 2024E Revenue = 804.029 × 1.22 | 980.9 | 980.9 | 980.9 |
| Enterprise Value | 3,923.7 | 4,414.1 | 4,904.6 |
| (+) net cash(现金 401.2 + 证券 811.9) | 1,213.1 | 1,213.1 | 1,213.1 |
| Pre-money Equity ÷ 143.7166m 股 | $35.74 | $39.16 | $42.57 |
| ×(1 − 12.5% discount)= 支持价 | **$31.27** | **$34.26** | **$37.25** |

交叉验证:peer 加权平均 4.52x → $34.38,与 midpoint 一致;SEC-03 公开初步区间 $31–$34 仅作 execution cross-check,拟议价位于其上限。

## 三、盈利质量(QoE)风险 —— Proceed 以本披露为前提

- 2023A Revenue 804.0(同比 +20.6%)、Net loss -90.8、承销 EBITDA -118.4(margin -14.7%)、FCF -84.8:亏损收窄但未转正;
- 广告收入集中度 98.1%,单一收入线对宏观与广告主预算波动敏感;
- 2024E 增长 22% 为内部假设,高于 2023 实际增速 20.6%;若兑现不足,支持区间将下移;
- 年末 net cash 1,213.1 构成估值支撑;restructuring 8.1 已含于管理口径调整,不重复处理。

## 四、发行结构与募集(@ $34;Base 不含 greenshoe)

| 项目 | Base | Full Greenshoe |
|---|---|---|
| Primary / Secondary / Greenshoe(m 股) | 15.2765 / 6.7235 / 0 | 18.5765 / 6.7235 / 3.3 |
| 公司 gross(仅 primary) | 519.4 | 631.6 |
| 承销费 5% + 固定费用 7.0 | -33.0 | -38.6 |
| **公司净募集 net primary proceeds** | **486.4** | **593.0** |
| Post-money 股数(m) | 158.99 | 162.29 |
| 新投资者稀释 | 9.61% | 11.45% |

Secondary 对应 228.6 归出售股东,不形成公司募集、不增加公司总股数;greenshoe 增量仅扣 5% 费(增量净募集 106.6),固定费用不重复计提。SEC-02 的 NTBV 11.17 / 即时稀释 21.33 基于假设价 $32.50,仅作交叉核对;$34 口径 NTBV 因缺 pre-money 账面净值基数标注"待核实"。

## 五、错误修正与口径冲突

Candidate_Model 共 11 行(含表头),10 条 legacy treatment 已全部修正(量化影响详见模型 Error_Audit 表):盈利高估 49.1;bridge 漏证券致每股低估 5.65(折后 4.94);22.0m 误全作 primary 致公司募集高估 228.6;greenshoe 误并入 Base(高估 3.3m 股 / 112.2 gross);费基误含 secondary(费用高估 11.4);post-money 股数虚增 6.72m;稀释分子分母口径不一致;建议未过 guardrail 而单边上移。口径冲突(管理 vs 承销 EBITDA、2023A vs 2024E 分母、$34 vs 公开区间、4.5x vs peer 加权 4.52x)已在模型显式记录双方数值,均以 Committee_Policy 为准取舍。

**待核实**:secondary 承销费承担方;债务余额(bridge 按 Policy 公式仅含现金+证券);pre-money 账面净值基数;greenshoe 行使机制细节。

**建议**:批准按 $34.00 推进发行(Proceed)。Base 口径公司净募集 486.4、新投资者稀释 9.61%;greenshoe 全行使单独情景净募集 593.0、稀释 11.45%。QoE 风险已如上文完整披露,定价距 midpoint 仅 $0.26,安全边际有限,建议路演中重点跟踪订单对区间上限的支撑。
