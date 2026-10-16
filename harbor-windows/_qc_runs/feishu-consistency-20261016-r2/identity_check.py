"""校验每个题包的当前身份（Harbor dirhash）与包内 jobs 记录的身份是否一致。

复用甲方 QC 脚本 inspect_delivery.py 的 harbor_dirhash / task_hash 实现。
只读计算，不修改任何文件。
"""
import json
import os
import sys
from pathlib import Path

HW = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
QC_SCRIPTS = HW / "_reference" / "windows-harbor-qc" / "scripts"
sys.path.insert(0, str(QC_SCRIPTS))

from inspect_delivery import harbor_dirhash, task_hash  # noqa: E402

OUT = HW / "_qc_runs" / "feishu-consistency-20261016-r2" / "identity-check.json"

rows = []
for pkg in sorted(p.name for p in HW.iterdir() if p.is_dir() and p.name.startswith("wfflab__")):
    root = HW / pkg
    rec = {"package": pkg}
    try:
        rec["current_dirhash"] = harbor_dirhash(root)
        rec["current_task_hash"] = task_hash(root)
    except Exception as exc:  # pragma: no cover
        rec["error"] = repr(exc)
        rows.append(rec)
        continue

    jobs = root / "jobs"
    if not jobs.is_dir():
        rec["jobs"] = "N/A (no jobs/)"
        rows.append(rec)
        continue

    report = jobs / "_index" / "assembly_report.json"
    job_checksums = []
    if report.is_file():
        doc = json.loads(report.read_text(encoding="utf-8"))
        job_checksums = sorted(set(doc.get("harbor_task_checksums") or []))
    rec["jobs_checksums"] = job_checksums
    rec["matches"] = job_checksums == [rec["current_dirhash"]]
    # 逐 job 的 lock/result 里记录的身份
    per_job = {}
    for name in sorted(os.listdir(jobs)):
        jd = jobs / name
        if not jd.is_dir() or name == "_index":
            continue
        for rel in ("verifier/result.json", "lock.json", "result.json"):
            p = jd / rel
            if p.is_file():
                try:
                    doc = json.loads(p.read_text(encoding="utf-8-sig"))
                except Exception:
                    continue
                cs = doc.get("harbor_task_checksum") or doc.get("task_checksum")
                if cs:
                    per_job[name] = cs
                    break
    rec["jobs_with_checksum"] = len(per_job)
    rec["distinct_job_checksums"] = sorted(set(per_job.values()))
    rec["per_job_all_current"] = bool(per_job) and set(per_job.values()) == {rec["current_dirhash"]}
    rows.append(rec)

OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

for r in rows:
    print("==== %s" % r["package"])
    print("   current dirhash : %s" % r.get("current_dirhash"))
    if "jobs" in r:
        print("   jobs            : %s" % r["jobs"])
    else:
        print("   jobs checksums  : %s" % (r.get("jobs_checksums") or "-"))
        print("   assembly match  : %s" % r.get("matches"))
        print("   per-job current : %s (%d jobs, %d distinct)" % (
            r.get("per_job_all_current"), r.get("jobs_with_checksum", 0),
            len(r.get("distinct_job_checksums") or [])))
