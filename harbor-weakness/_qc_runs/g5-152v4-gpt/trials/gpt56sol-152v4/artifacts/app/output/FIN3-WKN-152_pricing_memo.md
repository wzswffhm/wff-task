# Reddit IPO 定价复核备忘录

**日期：**2024-03-20（正式定价前）  **建议：Proceed**

## 结论与方法
委员会v3（CP-01至15）为现行政策。SEC事实为2023A收入804.029、现金401.176、证券811.946；22%增长、4.0x/4.5x/5.0x、12.5%折扣及$34均为内部假设。承销EBITDA为负，按CP-05采用EV/2024E Revenue：收入×(1+增长)×倍数，加现金及证券，除经济股数后施加折扣。支持区间$31.27–$37.25，中点$34.26；$34较中点signed -0.26、absolute 0.26。

## 盈利质量、结构与募集
管理层Adjusted EBITDA -69.275减SBC 49.086得承销EBITDA -118.361；重组8.098已调整，增量为零；FCF -84.838。Base公司gross/fee/net为519.401918/25.9700959/486.4318221，Full为631.601918/31.5800959/593.0218221；fee仅按primary gross，固定费用各情景仅一次。Base不含shoe，secondary 6.723473不形成公司募集或新增股。Post shares为158.993090/162.293090；primary/post-money为9.608%/11.446%。SEC-02仅核验$32.50−$11.17=$21.33，不外推$34 NTBV。

## 数据核验（逐异常一行）
- `monthly_revenue_2022_2023.csv`第9/14行、2022-08：重复57.100；SEC-01年数666.701为依据；剔除第14行，723.801→666.701。
- `monthly_revenue_2022_2023.csv`第15–27行、FY2023：All rows 870.529含两条12月；SEC优先；剔除INT第27行后804.029，原口径影响+66.500。
- `monthly_revenue_2022_2023.csv`第26/27行、2023-12：INT 66.500替换SEC 68.979会得801.550、差-2.479；CP-02以SEC为准，拒绝替换。
- `revenue_by_segment_2022_2023.csv`第5行、FY2023 Other：152.470为小数错位；`SEC-01_financials_extract.xlsx` Revenue/Other revenue行支持15.247；更正后总额804.029。
- `sbc_detail_2022_2023.csv`第6–10行、FY2023：components 49.086与TOTAL 49.680差0.594；components与SEC-01一致；拒绝TOTAL。
- `SEC-16_share_count_history.csv`第5行、2024-03-18：注册141.2无法由“排除RSU”重建（应138.000000）；委员会经济股143.716563与SEC-09组件一致；列治理例外，不用于估值。
- `cap_table_snapshot_20240318.csv`第2–5行、2024-03-18：SEC-09标签与`SEC-09_capitalization.csv`第2–7行的2024-03-11冲突；算术一致；保留委员会快照并标记血缘。
- `Source_Index.csv`全表：UW-01被`Offering_Terms_20240320.xlsx`第2–13行及cap table第6–8行引用但未收录；直接追踪并列治理例外。
- `Source_Index.csv`全表：缺9个实际文件ID（SEC-06, SEC-07, SEC-08, SEC-11, SEC-12, SEC-13, SEC-14, SEC-15, SEC-16）；以对应文件名直接追踪、不推定优先级，列治理例外。

## 决策
发行结构10项检查均由明确条件计算并通过；SEC-16及来源索引为披露的治理例外，不是发行结构hard error。$34通过区间、距中点及结构三项测试，按CP-14建议 **Proceed**。
