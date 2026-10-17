# -*- coding: utf-8 -*-
"""extract_qc_facts.py —— 从交付包 jobs/ 抽取填 quality-review 所需的全部事实。

只读。输出 JSON，供生成 14 项人工质量复核使用。
用法：python extract_qc_facts.py <package-dir> [out.json]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

GROUP_ORDER = ("F2P", "P2P")


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def main() -> int:
    pkg = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else pkg.parent / "_qc_facts.json"
    jobs = pkg / "jobs"

    facts: dict = {"package": str(pkg), "name": pkg.name}

    # ---- task identity -------------------------------------------------
    toml = (pkg / "task.toml").read_text(encoding="utf-8-sig", errors="replace")
    for key in ("version", "task_type", "docker_image"):
        m = re.search(rf'^\s*{key}\s*=\s*"?([^"\n]+)"?', toml, re.M)
        facts[key] = m.group(1).strip() if m else None
    m = re.search(r'^\s*id\s*=\s*"?([^"\n]+)"?', toml, re.M)
    facts["task_id"] = m.group(1).strip() if m else None

    # ---- judge / rubric hash -------------------------------------------
    rubric = pkg / "tests" / "rubric.json"
    judge = pkg / "tests" / "judge.toml"
    if rubric.is_file():
        facts["rubric_sha256"] = hashlib.sha256(rubric.read_bytes()).hexdigest()
    if judge.is_file():
        jt = judge.read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(r'source_sha256\s*=\s*"([0-9a-f]+)"', jt)
        facts["judge_source_sha256"] = m.group(1) if m else None
        facts["judge_rubric_count"] = len(re.findall(r"\[\[rubric\]\]", jt))

    # ---- required testcases --------------------------------------------
    rq = read_json(pkg / "tests" / "required_testcases.json")
    rows = rq if isinstance(rq, list) else (rq or {}).get("testcases") or []
    facts["required_total"] = len(rows)
    facts["required_groups"] = {}
    for r in rows:
        g = str((r or {}).get("group") or "?").upper()
        facts["required_groups"][g] = facts["required_groups"].get(g, 0) + 1

    # ---- per-job facts --------------------------------------------------
    checksums: set[str] = set()
    per_job = []
    if jobs.is_dir():
        for job in sorted(p for p in jobs.iterdir() if p.is_dir() and p.name != "_index"):
            rj = read_json(job / "result.json") or {}
            ver = read_json(job / "verifier" / "result.json") or {}
            mr = read_json(job / "agent" / "model-result.json")
            cases = ver.get("testcases") or []
            passed = sum(1 for c in cases if str(c.get("outcome")).upper() == "PASS")
            failed = [c.get("test_id") for c in cases
                      if str(c.get("outcome")).upper() == "FAIL"]
            cs = rj.get("task_checksum")
            if cs:
                checksums.add(cs)
            entry = {
                "job": job.name,
                "score": ver.get("score"),
                "validity": ver.get("status"),
                "cases_total": len(cases),
                "cases_passed": passed,
                "failed": failed,
                "task_checksum": cs,
                "task_version": ver.get("task_version"),
            }
            if mr:
                entry.update({"steps": mr.get("steps"), "output_tokens": mr.get("output_tokens"),
                              "elapsed_sec": mr.get("elapsed_sec"),
                              "stop": mr.get("last_stop_reason"),
                              "runner_sha256": mr.get("runner_sha256")})
            traj = job / "agent" / "trajectory.jsonl"
            if traj.is_file():
                txt = traj.read_text(encoding="utf-8-sig", errors="replace")
                entry["traj_events"] = len([l for l in txt.splitlines() if l.strip()])
                entry["traj_cjk"] = len(re.findall(r"[\u3400-\u9fff]", txt))
                entry["traj_has_banned_prefix"] = bool(
                    re.search(r"中文口语化提示\s*[：:]", txt))
                # 联网/取答案痕迹
                hits = re.findall(
                    r"(?i)\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|git\s+(?:clone|fetch|pull)|"
                    r"pip\s+install|choco|winget)\b", txt)
                entry["network_tool_hits"] = len(hits)
            per_job.append(entry)

    facts["jobs"] = per_job
    facts["job_count"] = len(per_job)
    facts["checksums"] = sorted(checksums)
    facts["checksum_unique"] = len(checksums) == 1

    # ---- scores ---------------------------------------------------------
    def score_of(job_name: str):
        for e in per_job:
            if e["job"] == job_name:
                return e["score"]
        return None

    qwen = [score_of("model-qwen-%d" % i) for i in (1, 2, 3)]
    opus = [score_of("model-opus-%d" % i) for i in (1, 2, 3)]
    facts["qwen_scores"] = qwen
    facts["opus_scores"] = opus
    facts["qwen_sum"] = sum(s for s in qwen if isinstance(s, int))
    facts["opus_sum"] = sum(s for s in opus if isinstance(s, int))
    facts["strict_gap_ok"] = facts["qwen_sum"] < facts["opus_sum"]
    facts["qwen_testcase_pass_sum"] = sum(
        e["cases_passed"] for e in per_job if e["job"].startswith("model-qwen-"))
    facts["opus_testcase_pass_sum"] = sum(
        e["cases_passed"] for e in per_job if e["job"].startswith("model-opus-"))
    facts["oracle"] = [{"job": e["job"], "score": e["score"], "validity": e["validity"]}
                       for e in per_job if e["job"].startswith("ctl-oracle-")]
    facts["nop"] = [{"job": e["job"], "score": e["score"], "validity": e["validity"],
                     "failed": e["failed"]} for e in per_job if e["job"].startswith("ctl-nop-")]

    # ---- zip / files ----------------------------------------------------
    facts["non_jobs_files"] = sum(
        1 for p in pkg.rglob("*") if p.is_file() and "jobs" not in p.parts)

    out.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(facts, ensure_ascii=False, indent=2))
    print("\n-> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
