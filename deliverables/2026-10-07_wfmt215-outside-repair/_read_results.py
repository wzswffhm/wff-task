import json, sys, glob, os

root = r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner\runs\wfflab__wfmt-215"
for d in sorted(glob.glob(os.path.join(root, "20261007T2234*"))):
    print("===", os.path.basename(d), "===")
    hits = glob.glob(os.path.join(d, "**", "result.json"), recursive=True)
    if not hits:
        print("  (no result.json yet)")
        continue
    for r in hits:
        try:
            j = json.load(open(r, encoding="utf-8"))
        except Exception as e:
            print("  parse err", e)
            continue
        for k in ("verdict", "report_status", "reason", "agent_status", "turns",
                  "duration_seconds", "weighted_score", "test_log_sha256"):
            if k in j:
                print("  ", k, "=", j[k])
