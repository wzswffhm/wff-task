# 贷款日终批处理 COBOL→Java 迁移

## 背景
你是银行核心系统组的开发工程师。行里要把一套运行多年的 COBOL 日终批处理（CLN-LOANACCR）迁移到 Java。这套程序每天晚上跑一次，为贷款账户计算利息并汇总多个口径的金额，结果交给下游入账系统。金额不能算错。你的任务是把这套程序（含它调用的子程序）完整迁移成单文件 Java，在样例数据上保证输出正确，并写一份说明迁移口径和验证方法的报告。

## 可用源文件（/app/input_files/，只读，共 59 份）
| 分组 | 文件 | 说明 |
| --- | --- | --- |
| 源码 | CLN-LOANACCR.CBL、CLN-DTUTIL.CBL | COBOL 主程序与子程序 |
| COPYBOOK | CLN-MASTER.CPY / CLN-TRAN.CPY / CLN-RATE.CPY / CLN-SCHED.CPY / CLN-CAL.CPY | 各文件记录布局 |
| 账户主档 | ACCT_MASTER_ML01.DAT ~ ACCT_MASTER_PL03.DAT（6 份，按产品拆分） | 账户主档，100 户，已脱敏 |
| 交易流水 | TRAN_HIST_01.DAT ~ TRAN_HIST_10.DAT | 交易流水，共 1336 笔 |
| 还款计划 | SCHED_01.DAT ~ SCHED_10.DAT | 还款计划，共 6672 条 |
| 利率调整 | RATE_ADJ_01.DAT ~ RATE_ADJ_05.DAT | 利率调整，共 61 条 |
| 节假日日历 | CAL_2016.DAT ~ CAL_2024.DAT | 节假日，共 87 个日期 |
| 汇率 | FX_RATE_USD.DAT | 汇率表（USD→CNY 季度汇率），32 行 |
| 运行日 | PROC_DATE.TXT | 本次运行日，内容为 20231231 |
| 参数表 | PROD_PARAM.DAT / CCY_PARAM.DAT / BASIS_CODE.DAT / STATUS_CODE.DAT / TRN_CODE.DAT / FEE_PARAM.DAT / TAX_PARAM.DAT / ORG_PARAM.DAT / BATCH_PARAM.DAT / GL_MAP.DAT | 业务参数与口径参考，程序须读取并做一致性校验 |

字段含义和业务口径以 COBOL 源码和 COPYBOOK 为准。样例数据已脱敏：客户名已替换为客户编码（如 CLIENT-0001），不包含任何真实个人信息。

## 交付物
| 文件名 | 是否必交 | 格式说明 |
| --- | --- | --- |
| COB-L4-002_LoanAccrual.java | 必交 | 单文件 Java 程序，JDK 21，只用标准库 |
| COB-L4-002_AccrualResult.txt | 必交 | 运行结果，100 行账户明细加 1 行汇总 |
| COB-L4-002_MigrationReport.md | 必交 | 迁移报告，Markdown |
| COB-L4-002_SummaryByCurrency.txt | 必交 | 分币种汇总：CNY/USD 各一行小计加 1 行 TOTAL |

## 任务要求
1. 通读 COBOL 主程序与子程序，把完整逻辑迁到 Java。
2. Java 从 /app/input_files 按目录模式读取全部数据文件（账户主档 ACCT_MASTER_*.DAT、交易 TRAN_HIST_*.DAT、利率调整 RATE_ADJ_*.DAT、还款计划 SCHED_*.DAT、日历 CAL_*.DAT、汇率 FX_RATE_USD.DAT、运行日 PROC_DATE.TXT，以及 PROD_PARAM/CCY_PARAM/BASIS_CODE/STATUS_CODE/TRN_CODE/BATCH_PARAM/FEE_PARAM/TAX_PARAM/ORG_PARAM/GL_MAP 参数表），用全部十类参数表（含 FEE_PARAM/TAX_PARAM/ORG_PARAM/GL_MAP）完成产品/币种/基准/状态/交易码/运行日/费用/税率/机构/科目映射的一致性校验，任一不一致必须报错退出；按与原程序相同的顺序处理，把明细结果写到 /app/output/COB-L4-002_AccrualResult.txt、分币种汇总写到 /app/output/COB-L4-002_SummaryByCurrency.txt。
3. 题目不提供原程序的期望输出。你需要用独立手段验证正确性（比如手算或复算关键片段、检查汇总与明细一致、本金不为负等），并把验证过程写进报告。
4. 报告要写清楚：迁移映射、你对业务口径的理解、验证方法、编译和运行命令。
5. 报告必须给出抽查核对表：至少 6 个代表性账户（覆盖 B30D 月末计息、跨 2020 闰年、利率调整生效、逾期宽限、停息、USD 汇率折算各至少 1 个），逐个列出 PRINCIPAL/NORMAL/PENALTY/ACCRUED 四列的复算过程与最终值，并与结果文件对应账户逐值一致。
6. 报告必须给出至少 1 个完整的手算窗口样例：从精确乘积、半进位舍入到累加的完整中间过程，证明每天独立舍入且中间不截断（正常应计与罚息应计各至少一个计息日）。

## 硬约束
- 三个交付物文件名逐字用上表，不能改名、不能加日期或版本号。
- 交付物都写到 /app/output/；/app/input_files/ 里的任何文件都不能改。
- Java 必须是单文件、只用 JDK 标准库，不能引第三方依赖。
- 结果文件每账户一行共 100 行，最后一行汇总；每行 14 个字段，顺序为：账户号、客户编码、产品、期末本金、正常应计、罚息应计、应计合计、已入账利息、已还本金、逾期本金、费用、罚息费用、计息基准、状态；客户编码左对齐补足 24 个字符。
- 报告用中文写，不超过 200 行，不要整段贴 COBOL 或 Java 源码。
- 报告和结果里不要出现身份证号、手机号、真实姓名等个人信息，也不要编造源文件里不存在的账户和金额。
- Java 程序必须对全部十类参数表做一致性校验（产品/币种/计息基准/状态码/交易码/运行日/费用/税率/机构/科目映射），任一不一致必须报错退出，不能只读取不校验。
- 报告里的验证数字、抽查金额、手算样例必须能在结果文件中溯源对应，禁止编造源文件中不存在的金额。

## 验收口径
- 输出满足：100 行账户明细加 1 行汇总，汇总与明细加总一致，本金不为负，逾期本金不超过本金，应计非负。
- 报告能说明迁移口径和验证方法。