# IPO 定价委员会发行前财务复核与定价建议

## 业务场景与角色

你是 IPO 承销团队的投行业务分析师。**2024 年 3 月 20 日**，定价委员会需要在正式定价前复核 Reddit, Inc. 的**盈利质量、估值区间与发行结构**，并判断当前拟议价格 **$34** 是否可以继续推进。

请以 **2024-03-20 为信息截止时点**，基于 `/app/input_files/` 下的材料修复工作底稿 `Candidate_Model`，并交付修正后的 IPO 模型与 Pricing Committee 备忘录。

不讨论发行承销协议的法律条款起草、路演营销方案与上市后市值管理安排。

## 一、已经确认的事实

1. **发行人**为 Reddit, Inc.，历史期为 2022A / 2023A，估值基准为 2024E Revenue；金额单位为 USD mm，股份单位为 mm shares，价格单位为 USD/share。
2. **信息集纪律**：Base case 仅可使用 2024-03-20 之前已获得的信息，以及附件中的**内部委员会假设**；**最终定价、发行完成后的 SEC 文件、上市后交易表现等后续结果一律不得进入 Base case**，也不得用于反推。
3. **控制口径**：`Committee_Policy` 工作表为本任务的控制口径，与 `Candidate_Model` 的旧处理冲突时**以 `Committee_Policy` 为准**；`Candidate_Model` 仅为旧工作底稿，**不应默认正确**。
4. **估值方法**：管理口径 Adjusted EBITDA 为非 GAAP 指标；`Committee_Policy` 规定 SBC 属持续性经济成本，承销口径不保留该加回。若按承销口径调整后 EBITDA 仍为负，主估值采用 **EV / 2024E Revenue**。
5. **发行结构**：Base 发行不假设 greenshoe exercise，full-exercise 情景须单独复核；secondary 不形成公司募集资金，也不增加公司总股数。
6. 全部输入材料位于 `/app/input_files/`（**只读**）；**除材料记载之外不得自行补充事实；无法核实之处应明确标注"待核实"**。

## 二、可用源文件

源文件为 `/app/input_files/Q7_题目.xlsx`，共 8 个工作表：

| 工作表 | 内容 | 在本次复核中的作用 |
|---|---|---|
| `README` | 复核时点、发行人、复核范围、单位与 Base 处理约定 | 任务边界与口径约定 |
| `Public_Financials` | 2022A / 2023A 收入、净利、Adjusted EBITDA、SBC、FCF、现金与有价证券等，含 `Source_ID` 溯源列 | 盈利质量与 equity bridge 取数 |
| `Offering_Terms` | Base 与 Full Greenshoe 两列的发行条款、费用、股数与状态开关 | 发行结构重建 |
| `Committee_Policy` | 信息集、QoE、估值、预测、发行、费用、委员会处置共 13 条约定 | **控制口径** |
| `Underwriting_Assumptions` | 2024E 增长率、peer 倍数区间、IPO discount、SBC 与重组处理 | 承销假设 |
| `Peer_Comps` | 5 家可比公司 NTM EV/Revenue 与权重 | 倍数区间交叉验证 |
| `Candidate_Model` | 11 条 legacy treatment、review point 与 status 的旧工作底稿 | **待修复对象** |
| `Source_Index` | SEC-01 ~ SEC-04、UW-01 的文件名、as-of 日期、事实与用途 | 来源优先级与截止日校验 |

## 三、工作成果及使用目的

该成果将用于定价委员会会议审议，决定本次发行是否按拟议价格推进。请完成以下内容：

1. **信息集冻结**：全程只使用 2024-03-20 前已公开的 SEC 材料与附件内的内部委员会假设；`Source_Index` 中各来源的 as-of 日期用于截止日校验。**须明确区分"SEC 公开事实"与"内部 Committee 假设"**，22% 增长、peer multiple、12.5% discount、内部 cap-table snapshot 与拟议 $34 均属内部假设，不得包装为 SEC 公开事实。
2. **盈利质量（QoE）复核**：复核 2023 年 Revenue、Net Loss、Adjusted EBITDA、SBC、Free Cash Flow 及 cash / marketable securities；按 `Committee_Policy` 口径撤销 SBC 加回，计算承销口径 EBITDA，并判断调整后 EBITDA 是否仍为负。
3. **估值区间测算**：若承销 EBITDA 仍为负，采用 2024E Revenue 为主估值分母，按 peer 区间 4.0x–5.0x 计算 Enterprise Value；经完整 net cash bridge（year-end cash + marketable securities）得到 pre-money equity，再统一应用 **12.5% IPO execution discount**，得出委员会支持的价格区间与 midpoint。
4. **发行结构重建**：重建 primary 15.276527m、secondary 6.723473m、greenshoe 3.3m 的 Base 发行结构；正确计算 company gross primary proceeds、承销费与固定费用后的 net primary proceeds、post-money shares 与稀释指标；**secondary 不得计入公司募集资金、不得增加总股数；greenshoe 不得预先并入 Base**，另列 full-exercise 情景。
5. **错误识别与修正**：逐条复核 `Candidate_Model`，在模型中记录所发现问题的类别、legacy 处理、正确处理与影响。
6. **勾稽一致性**：盈利质量、估值、募集、稀释与最终定价摘要各模块的核心结果须能相互勾稽，同一指标在不同模块的口径与数值一致。
7. **定价建议**：按 `Committee_Policy` 的处置规则，判断拟议 $34 应 **Proceed**、**Reprice** 还是 **Defer**，并在备忘录中说明支持的价格区间、盈利质量风险、发行结构与最终定价建议。
8. **可复算代码**：交付一个可直接运行的 Python 脚本，**从 `/app/input_files/Q7_题目.xlsx` 读入并计算全部结论数值**，不得硬编码任何结论数字、不得引用网络数据。

## 四、交付物要求

全部交付物写入 `/app/output/`，共 **3 项，全部必交**：

| 文件名 | 说明 |
|---|---|
| `FIN3-WKN-152_ipo_model.xlsx` | 主交付物：修复后的 IPO 模型。须至少包含 `Inputs`、`QoE`、`Valuation`、`Offering_Proceeds`、`Dilution`、`Pricing_Summary`、`Error_Audit` 七个可辨识的工作表（措辞可微调，但须能一一对应上述七个模块），各表填写实质内容并给出计算过程或取值来源 |
| `FIN3-WKN-152_pricing_memo.md` | Pricing Committee 备忘录，Markdown 格式，**不超过 2 页**（按 A4 排版估算，正文中文字符不超过 1,600 字，不含 Markdown 表格竖线与代码块标记），须说明支持的价格区间、盈利质量风险、发行结构与最终定价建议 |
| `FIN3-WKN-152_reproduce.py` | 可复算代码，从 `input_files` 读入并计算全部结论，运行后输出各项关键结果 |

## 五、硬约束

1. **信息集不得越界**：不得使用 2024-03-20 之后的最终发行结果、最终定价、发行完成后的 SEC 文件或上市后市场表现反推 Base case；拟议 $34 是决策输入，不是已实现结果。
2. **口径冲突必须显式处理**：同一指标在不同来源出现不同口径或数值时，须在模型中指出差异、给出双方数值与来源，并说明取舍依据；**不得静默择一使用，不得修改任何输入文件**。
3. **参数只能取自材料**：增长假设、倍数区间、discount 比例、费用结构、股数与 cap-table snapshot 均须可回溯到 `Committee_Policy` / `Underwriting_Assumptions` / `Offering_Terms` / `Source_Index`；**不得引入材料之外的假设或自设口径**，材料未载明的项目应标注"待核实"。
4. **不得虚构数据**：所有数值必须可回溯到 `/app/input_files/Q7_题目.xlsx` 中的具体工作表或由其中的数据计算得到；引用的来源须在 `Source_Index` 中真实存在。
5. **发行结构口径不得混淆**：`secondary` 不形成公司募集资金、不增加公司总股数；`greenshoe` 不预设进 Base，full-exercise 情景须单独列示；承销费按公司 primary gross proceeds 计提，固定费用不重复计提。
6. **复算脚本须可独立运行**：脚本从 `Q7_题目.xlsx` 读入并计算，不得硬编码结论数值；在容器内以 `python3 FIN3-WKN-152_reproduce.py` 方式运行时应能输出全部关键结果。
7. **交付物文件名必须与上表逐字一致**（大小写、下划线、连字符均不得改动），不得添加日期、版本号等动态成分；模型须为有效的 `.xlsx` 文件。
8. **备忘录篇幅**：严格不超过 2 页；篇幅超限视为不满足交付要求。
