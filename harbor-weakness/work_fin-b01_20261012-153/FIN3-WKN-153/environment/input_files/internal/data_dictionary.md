# 数据字典（2026-08 版）

## 1. 持仓明细 `portfolio/holdings_2026Q3.xlsx`

| 字段 | 含义 |
| --- | --- |
| `acct` | 资金账户代码 |
| `sec_code` | 证券编码（交易所 / 银行间统一编码） |
| `sec_name` | 证券名称 |
| `sec_type` | 券种类别，取值见 `security_master.csv` |
| `vol` | 期末持仓数量：债券为面值（元），基金份额为份额（份），非标为本金（元） |
| `as_of` | 数据所属日期 |
| `updated_at` | 导出时间 |
| `source_row_id` | 导出行编号，重复上报时该编号不同 |

## 2. 行情文件 `data/`（估值日行情）

| 字段 | 含义 |
| --- | --- |
| `instrument_id` | 证券编码，与持仓明细的 `sec_code` 为**同一编码体系** |
| `trade_date` | 交易日 |
| `close_price` | 收盘价 / 估值价：债券与非标为每百元面值价格，权益型基金为每份额净值 |
| `price_type` | 价格类型 |
| `batch_tag` | 推送批次标识 |

市值折算：债券与非标 `市值 = vol × close_price / 100`；
权益型基金 `市值 = vol × close_price`。

## 3. 命名沿革

历史文件曾以 `wind_code` 标识证券编码；2026-08 数据字典改版后，
持仓侧统一为 `sec_code`、行情侧统一为 `instrument_id`，两者一一对应，
不再存在 `wind_code` 列。旧版字段名仅在历史归档文件中保留。
