# wfflab__wreparse-217 · 飞书写回记录

- 写入时间：2026-10-07 14:45 (+08:00)
- 目标表：`https://vcnuhsx1gwu0.feishu.cn/wiki/O1qjw1qFRijaf8kal5scROn9nmc?table=tblRDxcGkblflMBA&view=vewA7TVSjk`（"windwos作业"）
- base（wiki obj_token）：`EsJebL8JJaf7g4sIbItcnMFgnvg`
- table：`tblRDxcGkblflMBA`
- **record_id：`reczz28KQU8reW2k`**（rev 1278；表内当前唯一记录）
- 操作身份：`--as user`，登录账号 `wff`（`ou_f4e4bc01ed9be1ef4cbaedcdf8f19d45`）
- 执行脚本：`generate-win/scripts/upload_feishu.ps1 -ConfirmWrite`

## 写入结果（read-back 已核验）

| 字段 | 字段 ID | 写入值 |
|---|---|---|
| 文本（自动编号） | `fldffCZZex` | `118`（系统生成） |
| 题目方向 | `fldiuFJbFr` | `Windows/文件系统（NTFS 重解析点）/PowerShell/缺陷修复` |
| 提示词 | `fldOv2xWDV` | `instruction.md` 全文（5411 B，逐字） |
| 标注员 | `flda4emMz7` | `wff`（user 字段，current_user 默认解析） |
| 状态 | `fldd6UxkAs` | `待提交` |
| oracle/nop截图 | `fldZI4BCU2` | `oracle_nop_controls.png`（96,778 B，token `NO1CbjLtJogapJxA4eIcW75In6g`） |
| 分数截图 | `fldg4yePGJ` | `score_summary.png`（61,010 B，token `MegpbVaCMoO7C8xwkkucc821nTd`） |
| 作业压缩包 | `fldnki9xts` | `wfflab__wreparse-217-v1.0.0.zip`（33,423 B，token `Tp14bqeEXo1IunxT68bcdK0tnB1`） |
| 领取日期 | `fldIsqG5qU` | 空（不写） |
| zhang质检 / xie质检 / 返修原因 | `fld4pYciTV` / `fldAk8Mdpe` / `fldWk8Ld9p` | 空（质检侧字段，不写） |

未写：自动编号字段、`提交/返修完成` 按钮字段（OpenAPI 不支持）。

## 包口径

按 `generate-win/references/feishu-delivery.md`：**默认上传 Harbor 四件套 ZIP**（`task.toml` / `instruction.md` / `environment/` / `tests/`）。已核对包内**不含** `solution/` 与 `source.json`，符合 `harbor-fourpiece.md` 的公开交付范围。

## 排障记录（重要）

首次执行失败：记录已创建（`reczz28KQU8reW2k`）但脚本在 read-back 阶段抛 `Invalid lark-cli JSON`，**附件未上传**。

- 根因：`upload_feishu.ps1` 内 `& lark-cli ... | Out-String` 读取原生 stdout 时，zh-CN 主机默认用 **GBK** 解码，而 lark-cli 输出是 **UTF-8** → 中文字段名变乱码（`oracle/nop鎴浘`），JSON 结构被破坏 → `ConvertFrom-Json` 失败。
- 处置：调用前设 `[Console]::OutputEncoding` / `$OutputEncoding` = UTF-8，并以 `-RecordId reczz28KQU8reW2k` 续跑（脚本会跳过已存在的附件），避免产生第二条记录。
- **已固化**：脚本开头新增两行编码前置（备份 `upload_feishu.ps1.bak-preencoding`，原 sha256 `1caf7dc1430189f1…`），`feishu-delivery.md` 补 "Host encoding (Windows)" 一节。
