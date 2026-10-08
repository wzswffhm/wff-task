"""Enrich package jobs/<job-id>/{agent,verifier} with the original runner evidence
kept in wff-task1, replacing the earlier "restated" placeholders.

For every jobs entry whose job_id also exists under
deliverables/2026-10-04_outside-harbor-win/runner/runs/<task>/<job_id>/<label>/,
the original per-run artefacts are copied in and the record flags are updated.
Nothing about the verdict is recomputed: test.log is verified by sha256 first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EVIDENCE = ("checks.json", "test.log", "stderr.log", "result.json")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--tasks", nargs="+", required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    report: list[dict] = []
    for task_id in args.tasks:
        jobs_dir = args.package / task_id / "jobs"
        runs_dir = args.runs / task_id
        if not jobs_dir.is_dir() or not runs_dir.is_dir():
            continue
        for job in sorted(p for p in jobs_dir.iterdir() if p.is_dir()):
            job_json = job / "job.json"
            if not job_json.is_file():
                continue
            run_dir = runs_dir / job.name
            if not run_dir.is_dir():
                continue
            doc = json.loads(job_json.read_text(encoding="utf-8-sig"))
            recorded = doc.get("test_log_sha256")
            logs = sorted(run_dir.rglob("test.log"))
            if not logs:
                continue
            digest = sha256_file(logs[0])
            if recorded and recorded != digest:
                report.append({"job_id": job.name, "task_id": task_id, "status": "sha256-mismatch",
                               "recorded": recorded, "actual": digest})
                continue

            label_dir = logs[0].parent
            copied: list[str] = []

            def copy(src: Path, dst: Path, tag: str) -> None:
                if src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(src.read_bytes())
                    copied.append(tag)

            for name in EVIDENCE:
                copy(label_dir / name, job / "verifier" / name, f"verifier/{name}")
            copy(label_dir / "agent.log", job / "agent" / "agent.log", "agent/agent.log")

            run_json = job / "agent" / "run.json"
            if run_json.is_file():
                run_doc = json.loads(run_json.read_text(encoding="utf-8-sig"))
                run_doc["artifacts_present"] = True
                run_doc["artifacts_note"] = (
                    "original per-run artefacts restored from the local runner store "
                    "(agent/agent.log, verifier/checks.json, verifier/test.log, verifier/stderr.log)"
                )
                run_doc["raw_label_dir"] = str(label_dir)
                run_json.write_text(json.dumps(run_doc, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
                copied.append("agent/run.json")

            result_json = job / "verifier" / "result.json"
            if result_json.is_file():
                res_doc = json.loads(result_json.read_text(encoding="utf-8-sig"))
                res_doc["raw_log_present"] = True
                res_doc["raw_log_note"] = (
                    "original test.log / checks.json / stderr.log restored from the local runner store"
                )
                res_doc["raw_label_dir"] = str(label_dir)
                result_json.write_text(json.dumps(res_doc, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
                copied.append("verifier/result.json")

            doc["evidence_restored"] = True
            doc["evidence_files"] = sorted(set(copied))
            doc["evidence_source"] = str(label_dir)
            job_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            report.append({"job_id": job.name, "task_id": task_id, "status": "enriched",
                           "files": sorted(set(copied))})

    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    enriched = sum(1 for r in report if r["status"] == "enriched")
    print(f"enriched={enriched} mismatch={sum(1 for r in report if r['status'] == 'sha256-mismatch')}")
    for entry in report:
        if entry["status"] == "sha256-mismatch":
            print("  MISMATCH", entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
