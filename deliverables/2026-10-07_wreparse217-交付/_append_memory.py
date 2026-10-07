import pathlib

log = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\memory\2026-10-07.md")
text = """
### C. 217 题包飞书交付（14:40–14:47，用户指令「将 217 的题包交付到飞书…标注员填 wff」）

- 目标表：wiki `O1qjw1qFRijaf8kal5scROn9nmc?table=tblRDxcGkblflMBA` → base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA`（"windwos作业"，交付前为**空表**）。
- 写入记录 **`reczz28KQU8reW2k`**（auto_number 编号 118）：
  - 题目方向 `Windows/文件系统（NTFS 重解析点）/PowerShell/缺陷修复`
  - 提示词 = `instruction.md` 全文（5411 B，逐字）
  - 标注员 = `wff`；状态 = `待提交`
  - oracle/nop截图 = `oracle_nop_controls.png`(96778)；分数截图 = `score_summary.png`(61010)；作业压缩包 = `wfflab__wreparse-217-v1.0.0.zip`(33423)
  - 领取日期 / zhang质检 / xie质检 / 返修原因 留空（质检侧字段不写）
- 包口径：按 `generate-win/references/feishu-delivery.md` 默认传 **Harbor 四件套 ZIP**；已核对包内无 `solution/`、无 `source.json`，符合 `harbor-fourpiece.md`。
- **★★ 坑（已固化）**：`upload_feishu.ps1` 在 zh-CN 主机上把 lark-cli 的 UTF-8 stdout 按 **GBK** 解码 → 中文字段名乱码（`oracle/nop鎴浘`）→ `ConvertFrom-Json` 抛 `Invalid lark-cli JSON`；**此时记录已创建但三个附件全未上传**。处置：调用前设 `[Console]::OutputEncoding` / `$OutputEncoding` = UTF8，并以 `-RecordId reczz28KQU8reW2k` **续跑**（脚本会跳过已存在附件）→ 附件补齐、read-back verified=true。修复已写进脚本（备份 `upload_feishu.ps1.bak-preencoding`，原 sha256 `1caf7dc1430189f1…`），`feishu-delivery.md` 补 "Host encoding (Windows)" 一节。
- 产物：`deliverables/2026-10-07_wreparse217-交付/FEISHU_WRITEBACK.md`（字段/附件 token/排障全记录）。
- 顺带复查同 automation 的 QWEN 探针（tag `wfq`）：容器 `oh-20261007t141452-…-01` Up 31 min，run01 进行中，**无 `matrix-wfq.done`** → 按既定策略不启动新分片、不干预。
"""
with log.open("a", encoding="utf-8") as fh:
    fh.write(text)
print("daily log +", len(text), "chars")

am = pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\memory\automations"
    r"\fed023f6-1b9c-489c-854d-c3515c9cb0b9\memory.md"
)
am_text = """
## 2026-10-07 14:47 — 217 题包飞书交付完成（本 automation 的 217 线彻底收口）

**用户指令**：「将 217 的题包交付到飞书 <wiki O1qjw1qFRijaf8kal5scROn9nmc?table=tblRDxcGkblflMBA> 中，标注员填 wff」。

**结果**：record **`reczz28KQU8reW2k`**（编号 118，表内唯一记录）——题目方向 `Windows/文件系统（NTFS 重解析点）/PowerShell/缺陷修复`；提示词 = `instruction.md` 全文；标注员 `wff`（user 字段 current_user 自动解析）；状态 `待提交`；三附件 `oracle_nop_controls.png` / `score_summary.png` / `wfflab__wreparse-217-v1.0.0.zip`（四件套 ZIP，无 solution/ 无 source.json）。read-back 全部通过。质检侧字段（领取日期/zhang质检/xie质检/返修原因）留空。**未写飞书之外的任何系统**。

**★ 新坑（已固化）**：`generate-win/scripts/upload_feishu.ps1` 在 zh-CN 主机默认按 GBK 解码 lark-cli 的 UTF-8 stdout → 中文字段乱码 → `ConvertFrom-Json` 抛 `Invalid lark-cli JSON`，**而记录已建、附件未传**。修复 = 脚本内加 `[Console]::OutputEncoding` / `$OutputEncoding` = UTF8（备份 `.bak-preencoding`）；补救 = 用 `-RecordId` 续跑。

**下次（HOURLY）要点（仍是 wfmt-215 线；217 已闭环、勿再动）**：
1. 查 `runner/logs/matrix-wfq.done`。未生成 → 只在 `ROUND_WFMT_STATUS.md` 追加一行进度（Windows 侧 `docker ps` + 日志尾部），**绝不启动新分片**。本次复查（14:47）：容器 Up 31 min，run01 进行中。
2. 已生成 → `summarize_model_runs.py --workspace-root <runner> --task-id wfflab__wfmt-215 --after <epoch> --control-runs 3`（**必须带 `--after`**）→ `logs/_wfqsummary.json`：`models.QWEN.score_sum` ≤2 → 起 OPUS×3（tag `wfo`）期望 3>2；=3 → 调题面后重跑。
3. epoch = `2026-10-07T06:12:40+00:00`（controls 起跑 UTC）。容器核对只用 Windows 侧 docker。⛔ 不调难度/turn；⚠️ 计划任务用毕 `Disable-ScheduledTask`。
4. **日后还要往飞书写行**：控制台 UTF-8 已在脚本内固化，直接 `upload_feishu.ps1 -ConfirmWrite` 即可。
"""
with am.open("a", encoding="utf-8") as fh:
    fh.write(am_text)
print("automation memory +", len(am_text), "chars")
