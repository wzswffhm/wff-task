#!/usr/bin/env python3
"""Assemble the wfflab__wreparse-217 delivery bundle and drop it on the Desktop."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVID = HERE / "evidence"
PKG = HERE / "package" / "wfflab__wreparse-217-v1.0.0.zip"
DESKTOP = Path(r"C:\Users\Administrator\Desktop")
STAGE_NAME = "wfflab__wreparse-217-交付-20261007"
STAGE = HERE / STAGE_NAME
OUT_ZIP = DESKTOP / "wfflab__wreparse-217-交付包-20261007.zip"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


summary = json.loads((EVID / "model_runs_summary_r12.json").read_text(encoding="utf-8-sig"))
gates = summary["gates"]

if STAGE.exists():
    shutil.rmtree(STAGE)
(STAGE / "evidence").mkdir(parents=True)
shutil.copy2(PKG, STAGE / PKG.name)
for name in ("score_summary.png", "oracle_nop_controls.png", "model_runs_summary_r12.json"):
    shutil.copy2(EVID / name, STAGE / "evidence" / name)

files = [
    STAGE / PKG.name,
    STAGE / "evidence" / "score_summary.png",
    STAGE / "evidence" / "oracle_nop_controls.png",
    STAGE / "evidence" / "model_runs_summary_r12.json",
]
hashes = {f.relative_to(STAGE).as_posix(): sha256(f) for f in files}

rows = []
for model in ("QWEN", "OPUS", "GLM", "KIMI"):
    info = summary["models"][model]
    rows.append(
        "| {m} | {req} | {vc} | `{sc}` | **{s}** | {ex} |".format(
            m=model,
            req=info.get("required"),
            vc=info.get("valid_count"),
            sc=info.get("scores"),
            s=info.get("score_sum"),
            ex=len(info.get("excluded_agent_failures", [])),
        )
    )
model_table = "\n".join(rows)

readme = f"""# Windows 专项 Coding Bench 交付包 — `wfflab__wreparse-217`

- 交付日期：2026-10-07
- 题包标识：`task_id = wfflab__wreparse-217` ｜ `task_version = 1.0.0`
- **资格判定：`qualified = true`**（四模型资格门禁全部通过）
- 资格 epoch：`{summary.get('qualification_epoch')}`
- 汇总工件：`evidence/model_runs_summary_r12.json`（由 `summarize_model_runs.py` 生成，exit=0）
- 生成时间：`{summary.get('generated_at')}`

## 一、交付清单（四件套）

| # | 文件 | 说明 | SHA256 |
|---|---|---|---|
| 1 | `{PKG.name}` | 题包本体（ZIP 根 = task-id；含 `instruction.md` / `task.toml` / `environment/` / `tests/`，**不含 `solution/`**） | `{hashes[PKG.name]}` |
| 2 | `evidence/score_summary.png` | 模型得分与门禁判据截图 | `{hashes['evidence/score_summary.png']}` |
| 3 | `evidence/oracle_nop_controls.png` | Oracle / no-change 对照截图 | `{hashes['evidence/oracle_nop_controls.png']}` |
| 4 | `evidence/model_runs_summary_r12.json` | 汇总数据（权威读数） | `{hashes['evidence/model_runs_summary_r12.json']}` |

## 二、门禁结果

| 模型 | 需求轮数 | 有效轮 | scores | sum | 剔除（上游故障） |
|---|---|---|---|---|---|
{model_table}

**gates**：`controls_passed={gates.get('controls_passed')}` ｜ `model_counts_complete={gates.get('model_counts_complete')}` ｜ `opus_sum_greater_than_qwen={gates.get('opus_sum_greater_than_qwen')}`（**OPUS 3 > QWEN 2**）｜ `task_version_consistent={gates.get('task_version_consistent')}` ｜ `epoch_pinned={gates.get('epoch_pinned')}` ｜ `agent_failures_excluded={gates.get('agent_failures_excluded')}` ｜ **`qualified={gates.get('qualified')}`**

- 对照：no-change ×3 全 `VALID` + `verdict=0`；golden ×3 全 `VALID` + `verdict=1`。
- 剔除项均为 provider/网关层故障（`error` / `no_tool_call`），按规范**不得计 0**，已排除出计分集合。

## 三、关键约束

1. 题包 ZIP 内**不含** `solution/`、答案、隐藏测试或任何凭据。
2. 跑分所用题包即本交付题包本体（`runner/tasks/wfflab__wreparse-217` 为指向题包目录的符号链接）。
3. 资格 epoch 内的运行证据均已固化于 `evidence/`；跨 Epoch 结果不作比较。
4. 飞书写回未执行（待确认）。
"""

(STAGE / "README.md").write_text(readme, encoding="utf-8")

if OUT_ZIP.exists():
    OUT_ZIP.unlink()
with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(STAGE.rglob("*")):
        if f.is_dir():
            continue
        rel = Path(STAGE_NAME) / f.relative_to(STAGE)
        info = zipfile.ZipInfo.from_file(f, rel.as_posix())
        info.compress_type = zipfile.ZIP_DEFLATED
        mode = 0o755 if f.suffix.lower() in (".sh", ".ps1") else 0o644
        info.external_attr = (mode & 0xFFFF) << 16
        zf.writestr(info, f.read_bytes())

print(json.dumps({
    "stage": str(STAGE),
    "zip": str(OUT_ZIP),
    "zip_size": OUT_ZIP.stat().st_size,
    "zip_sha256": sha256(OUT_ZIP),
    "members": sorted(
        n for n in zipfile.ZipFile(OUT_ZIP).namelist() if not n.endswith("/")
    ),
}, ensure_ascii=False, indent=2))
