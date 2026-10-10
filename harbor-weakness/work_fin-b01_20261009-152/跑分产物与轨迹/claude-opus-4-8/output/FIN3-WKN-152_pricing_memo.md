# Pricing Committee 备忘录 — Reddit, Inc. IPO 发行前定价复核

**信息截止时点**：2024-03-20（正式定价前） · **发行人**：Reddit, Inc.（CIK 0001713445）
**控制口径**：`Committee_Policy_v3_20240320`（v2 已被取代：CP-03 SBC、CP-07 peer 区间、CP-09 折扣、CP-12 费基）
**单位**：USD mm / mm shares / USD per share

## 一、定价建议：**Proceed**

- 委员会支持区间（EV/2024E Revenue × 执行折扣后，每股）：**Low $31.27 / Mid $34.26 / High $37.25**，midpoint **$34.26**。
- 拟议价 **$34.00** 位于支持区间内，距 midpoint **$0.26**（≤ $0.50，CP-14）；发行结构无未解决 hard error。
- 结论依 CP-14：**Proceed**，但须在定价材料中明确披露下述盈利质量风险。

拟议 $34 为委员会决策输入，非已实现结果；最终定价与上市后表现未进入 Base。22% 增长、4.0–5.0x 倍数、12.5% 折扣、$34 及 cap-table snapshot 均为**内部假设**，非 SEC 公开披露事实。

## 二、估值推导（控制口径）

- 2024E Revenue = 2023A 804.029 ×(1+22%) = **980.915**（CP-06 内部假设）。
- 承销口径 EBITDA 仍为负 → 主估值用 EV/2024E Revenue（CP-05），不使用 EV/EBITDA。
- Pre-money Equity = EV + 现金 401.176 + 有价证券 811.946（CP-08，分列计入）。
- Pre-money 经济股数 143.716563；对未折价每股价值统一施加 12.5% 执行折扣（CP-09）。
- Mid：EV 4414.119 → Pre-money Eq 5627.241 → /sh 39.155 ×0.875 = **$34.26**。

## 三、盈利质量风险（CP-13，须披露）

- 2023A 净亏损 **-90.824**；管理层 Adjusted EBITDA **-69.275**。
- 承销口径 EBITDA = -69.275 − SBC 49.086 = **-118.361**（CP-03：SBC 为持续性成本，不加回）。
- 重组 8.098 已含于管理层口径，不二次加回（CP-04）。
- 2023A 自由现金流 **-84.838**（亦为负）。承销口径 EBITDA 与 FCF 双负为核心风险。

## 四、发行结构与募集

- Base：primary 15.276527m、secondary 6.723473m；greenshoe 3.3m 不计入 Base（CP-11，单列 full-exercise）。
- Secondary 不形成公司募集资金、不增加公司总股数（CP-10）。
- 公司 primary gross = **519.402**；承销费 5%×primary gross = 25.970；固定费用 7.000（不重复计提）；**net primary = 486.432**。
- Full-exercise：primary gross 631.602，net 593.022；greenshoe 增量净额 106.590（仅扣 5% fee）。
- 股本桥：Base post-money **158.993m**（新股占比 9.61%）；Full **162.293m**（11.45%）。SEC-02 稀释（NTBV $11.17 / 稀释 $21.33 @ $32.50）仅作交叉验证，不用于 $34 定价。

## 五、数据核验（明细 vs SEC-01 年度数，一行一条）

- `monthly_revenue_2022_2023.csv` 第14行：2022-08（57.100）重复，原始合计 723.801；去重后 666.701 勾稽 SEC-01 → 删除重复行。
- `monthly_revenue_2022_2023.csv` 第27行：2023-12 另有 INT-01 值 66.500（SEC-01 为 68.979）；INT-01 优先级 9 仅参考 → 按 CP-02 剔除，SEC-01 合计 804.029。
- `revenue_by_segment_2022_2023.csv` FY2023 Other=152.470（应为 15.247），分部合计 941.252 偏高 137.223 → 采 SEC-01 Other 15.247，拒用该明细行。
- `sbc_detail_2022_2023.csv` 第10行 FY2023 TOTAL=49.680，与分项合计 49.086 及 SEC-01 不符 → 采分项合计 49.086，拒用 TOTAL 行。
- `cap_table_snapshot_20240318.csv`：分项合计 143.716563 勾稽经济 TOTAL；SEC-09 注册股数 141.200 为口径差异（不含未结算 RSU），非错误。
- 其余勾稽（分部 FY2022、地区 FY2022/2023、SBC FY2022、季度 FY2023）差额为 0。

## 六、材料清点

`/app/input_files/` 共 **60** 个文件，分布于 **8** 个来源目录：committee 8、comps 4、financials 14、internal 6、legacy 4、research 5、sec_filings 17、根目录 2（分项之和 60，与总数勾稽）。

## 七、旧底稿错误（Candidate_Model_v0，共 12 类，详见 Error_Audit 表）

QoE 直用管理层口径；分母用 2023A；净现金桥漏有价证券；全股视为 primary；greenshoe 预并入 Base；费基含 secondary；secondary 计入总股数；secondary 所得计入公司现金；稀释分子分母口径不一致；依 peer-high 上调定价；#REF! 失效引用；沿用 v2 失效参数。均已按 v3 更正。
