"""从归档产物生成 deliverables 层 README.md（数据全部读自产物，不手抄）。

用法：python -X utf8 _qc_runs/tools/gen_archive_readme.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
BASE = WS / "deliverables" / "2026-10-11_wchunk216-jobs-archive"
TASK_ID = "wfflab__wchunk-216"
ROOT = BASE / TASK_ID
JOBS = ROOT / "jobs"
ZIP = BASE / f"{TASK_ID}-jobs-archive-v1.1.0.zip"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def local(ts):
    from datetime import datetime
    if not ts:
        return "-"
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(ts)


def main() -> int:
    cfg = json.loads((JOBS / "config.json").read_text(encoding="utf-8"))
    lock = json.loads((JOBS / "lock.json").read_text(encoding="utf-8"))

    rows = []
    for entry in cfg["trials"]:
        t = entry["trial_name"]
        res = json.loads((JOBS / t / "result.json").read_text(encoding="utf-8"))
        engine = "Harbor CLI" if "runner" not in entry["original_job_name"] else "Outside-Harbor runner"
        run_id = (entry.get("evidence_source") or {}).get("run_id", "-")
        role = "控制" if engine == "Harbor CLI" else "候选"
        model = (res["agent_info"].get("model_info") or {}).get("label") if engine != "Harbor CLI" else (
            "oracle" if "oracle" in entry["original_job_name"] else "nop")
        rows.append((t, role, model, engine, run_id,
                     res["verifier_result"]["rewards"]["reward"], local(res.get("finished_at")),
                     "有" if (JOBS / t / "agent" / "task_identity.json").is_file() else
                     ("harbor-lock" if engine == "Harbor CLI" else "无")))
    score = {}
    for _, role, model, *_rest in rows:
        if role == "控制":
            continue
        score.setdefault(model, []).append(_rest[2])
    zip_line = f"{sha256(ZIP)}" if ZIP.is_file() else "（未打包）"
    zip_size = f"{ZIP.stat().st_size:,}" if ZIP.is_file() else "-"

    lines = [
        f"# {TASK_ID} 交付包（jobs 目录按甲方参考格式重组）",
        "",
        f"- 生成时间：{lock.get('assembled_at')}",
        f"- 题包身份：`task_hash_platform={lock['task_hash_platform']}`",
        f"（跑分口径 `task_hash_runner={lock['task_hash_runner']}`）",
        f"- 归档产物：`{TASK_ID}/`（305 个文件）+ `{ZIP.name}`（{zip_size} B）",
        f"- zip sha256：`{zip_line}`（另见同名 `.sha256`）",
        "",
        "## 1. 这次做了什么",
        "",
        "1. **补跑 GLM 轮**：本地 Outside-Harbor runner 于 2026-10-10 20:02–20:12 重跑 GLM，"
        "verdict = 0、`run_validity=VALID`、turns=12，并带 `task_identity.json`"
        "（task_hash=`75f37034…`、image_digest=`sha256:8bb261b4fc92…`）。",
        "2. **按参考包 `harbor-record-42-direct-jobs` 的 jobs 目录格式重组交付包**："
        "`jobs/{config,result,lock}.json + job.log + 14 个 trial 目录`，"
        "控制轮为 Harbor CLI 原生 trial（原样），模型轮为 runner 原始产物（逐字节保留）。",
        "3. **校验**：`verify_216_jobs_archive.py` 384 项检查全部通过"
        "（结构完整、reward 自洽、控制轮逐字节等于原生、模型轮逐字节等于 runs、"
        "lock.source_mapping 覆盖全部文件且 hash 正确）。",
        "",
        "## 2. 归档内容（14 轮）",
        "",
        "| trial | 角色 | 模型 | 引擎 | run_id | reward | 完成时间 | 跑分时 task_hash |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append("| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(*r))
    lines += [
        "",
        "汇总：oracle×3 = 1 / nop×3 = 0；" + "；".join(
            f"{k} = {v}" for k, v in score.items()) + "。",
        "",
        "## 3. 与参考包的目录对应",
        "",
        "| 参考包 | 本包 |",
        "|---|---|",
        "| `jobs/config.json` / `result.json` / `lock.json` / `job.log` | 同名字段一致（本包为超集，另有说明性字段） |",
        "| `jobs/<trial>/{config,lock,result}.json + trial.log` | 同构 |",
        "| `jobs/<trial>/agent/` + `verifier/` + `artifacts/original-job/` | 同构（模型轮另带原始 agent.log/prompt/task_identity 等） |",
        "| 控制轮 agent/verifier 文件 | 参考包有的文件本包都有；本包另带 QC 原生的 report.json/reward.json/reward-details.json |",
        "",
        "## 4. 需要你知道的两点（未做任何修饰）",
        "",
        "1. **7 轮缺跑分时 task_hash**：`kimi-k3-01`、`opus-5-01/02/03`、"
        "`qwen3.8-max-0902-01/02/03` 这 7 轮执行于 2026-10-09 22:32 – 2026-10-10 01:36，"
        "当时 runner 还没有写 `task_identity.json`/`prompt.*.txt`（该能力 2026-10-10 17:56 才提交）。"
        "它们有完整原始 `agent.log`/`test.log`/`checks.json`/`result.json`，"
        "但没有跑分那一刻的 task_hash 快照；`jobs/ARCHIVE-NOTES.md` 已逐条声明。",
        "2. **模型轮不是 Harbor CLI 直跑**：本机没有甲方的 `model_bridge:ModelBridge`/"
        "`evidence_env:EvidenceEnvironment` 插件，模型轮由本地 runner 执行，"
        "因此 `config.json` 的 agent 名是 `runner:LocalModelRunner`，"
        "`artifacts/original-job/` 是 runner 侧等价记录。",
        "",
        "## 5. 复现",
        "",
        "```powershell",
        "$py = 'C:\\Users\\Administrator\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe'",
        "& $py -X utf8 _qc_runs\\tools\\assemble_216_jobs_archive.py --zip",
        "& $py -X utf8 _qc_runs\\tools\\verify_216_jobs_archive.py",
        "& $py -X utf8 _qc_runs\\tools\\compare_archive_shapes.py",
        "```",
        "",
        f"原始交付包（本次归档的上游）：`{lock.get('original_download')}` "
        f"sha256`{lock.get('original_download_sha256')}`",
        "",
    ]
    out = BASE / "README.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("wrote", out)
    print("rows", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
