# 数据字典（Data Dictionary）

| 字段 / 文件 | 含义 | 单位 | 备注 |
|---|---|---|---|
| `fy` | 财政年度 | — | FY2022 / FY2023 |
| `month` | 自然月 | YYYY-MM | — |
| `revenue_usd_mm` | 收入 | USD mm | 见各表口径说明 |
| `Source_ID` | 来源编号 | — | 对应 `sec_filings/Source_Index.csv` |
| `NTBV/share` | 每股有形账面净值 | USD/share | 仅在假定发行价 $32.50 下测算 |
| `immediate dilution` | 即时稀释 | USD/share | 同上 |

> 各底表按不同批次导出并多次修订，同一序列可能混有来自不同来源、不同时点的记录。
> 取数时以 `sec_filings/Source_Index.csv` 的来源优先级与 SEC 摘录的年度数为准。
