# Feishu delivery

## Default destination

- Base token: `EsJebL8JJaf7g4sIbItcnMFgnvg`
- Table ID: `tblRDxcGkblflMBA`
- View ID: `vewA7TVSjk`

## Fields

| Field | ID | Use |
| --- | --- | --- |
| 题目方向 | `fldiuFJbFr` | Windows domain/language/task category |
| 提示词 | `fldOv2xWDV` | Exact participant-facing `instruction.md` |
| 状态 | `fldd6UxkAs` | Default `待提交` |
| oracle/nop截图 | `fldZI4BCU2` | `oracle_nop_controls.png` |
| 分数截图 | `fldg4yePGJ` | `score_summary.png` |
| 作业压缩包 | `fldnki9xts` | Harbor four-piece ZIP by default; standard Task ZIP only when explicitly requested |

Do not write the auto-number field or the submit button field.

## Read-before-write

Before selecting a task, list all records and inspect at least `题目方向`, `提示词`, and `状态`. Compare title, prompt semantics, repository, and issue/commit identity. If duplicated, abandon the candidate and check the next candidate before creating files.

## Write sequence

1. Create or update the record with direction, prompt, and status.
2. Upload the Oracle/NOP screenshot.
3. Upload the score screenshot.
4. Upload the Harbor four-piece ZIP by default; upload the standard Task delivery ZIP, including `outside_harbor` and `delivery-extras`, only when that broader scope was explicitly requested.
5. Read the record back with the three attachment fields projected.
6. Verify attachment names and non-zero sizes.

Use `lark-cli --as user`. Never log or persist access tokens. If OAuth has expired, stop for user authorization and resume the same upload after authorization.
