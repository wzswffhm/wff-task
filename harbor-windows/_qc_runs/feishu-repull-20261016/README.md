# 从飞书重拉题包（2026-10-16）

用户指令：**“本地的题包清理掉从飞书上重新拉，218 和 221 除外”**。

## 本次动作

| 包 | 处理 | 结果 |
|---|---|---|
| `wfflab__wsparse-215-v1.0.0-delivery` | 删除本地目录 → 用飞书最新附件重建 | 逐文件 SHA256 与 ZIP 一致（273 文件） |
| `wfflab__wvas-216-v1.0.0-delivery` | 同上 | 一致（259 文件）；本地原有 2 个文件已备份 |
| `wfflab__wcancel-219-v1.0.0-delivery` | 同上 | 一致（260 文件） |
| `wfflab__wciocp-220-v1.0.0-delivery` | 同上 | 一致（258 文件） |
| `wfflab__wspawn-218-v1.0.0-delivery` | **保留本地，未动** | — |
| `wfflab__wtoken-221-v1.0.0-delivery` | **保留本地，未动**（其模型轮当时仍在运行） | — |

拉取方式：`lark-cli base +record-download-attachment`（record / file_token 见
`repull-result.json` 与 `feishu-consistency-20261016/feishu-upload-times.json`）→ 原样解压到
`harbor-windows/`，包内顶层目录自然落地，目录名 = 附件名去 `.zip`。

## 关键提示

1. **216 的本地独有文件已备份**：`preserved-from-local/wfflab__wvas-216-v1.0.0-delivery/`
   - `REFIT-2026-10-14.md`（11,623 B）
   - `verifier/WINDOWS_VALUE.md`（6,175 B）
   这两个文件参与题包身份计算（`harbor_dirhash` 覆盖 `jobs/` 以外的全部文件）。它们不在飞书附件里，
   因此重拉后的 216 包身份变为 `80ae0a3d…`，而包内 12 个 job 记录的仍是 `253161fb…`，
   甲方 QC 的 jobs 门禁会报 `run against a different Task checksum`（已实测：结论 FAIL）。
2. 215 / 219 / 220 重拉前后与飞书逐字节相同，无文件丢失，静态门禁仍全部 PASS。
3. 本次只做清理与重建，**未提交 git**；仓库里会体现为这 4 个包目录的改动。

## 产物

- `zip/`：本次重新下载的 4 个飞书交付附件
- `repull-dry-run.json`：执行前预演（含“本地独有文件/内容差异”清单）
- `repull-result.json`：执行结果（含每个包的 ZIP SHA256、文件数、复验结论）
- `repull_targets.py`：执行脚本（带白名单与路径断言，只允许动 `harbor-windows/` 下这 4 个目录）
- `preserved-from-local/`：被移出题包目录的本地独有文件备份
