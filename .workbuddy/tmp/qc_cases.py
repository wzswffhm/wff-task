"""从 QC report.json 提取 formal_results 里的 testcase 明细。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")


def show(name):
    p = Q / name / "report.json"
    if not p.is_file():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 90)
    print(f"## {name}   conclusion={d.get('conclusion')}")
    for t in d.get("tasks") or []:
        if isinstance(t, dict) and t.get("required_testcases"):
            rq = t["required_testcases"]
            f2p = sum(1 for x in rq if x.get("group") == "F2P")
            print(f"  {t.get('task_id')}: required={len(rq)} (F2P {f2p} / P2P {len(rq)-f2p})")
    for r in d.get("runs") or []:
        if not isinstance(r, dict):
            continue
        for fr in r.get("formal_results") or []:
            cases = fr.get("cases") or []
            passed = [c["id"] for c in cases if str(c.get("status")).upper() == "PASS"]
            failed = [c["id"] for c in cases if str(c.get("status")).upper() != "PASS"]
            print(f"  [{r.get('agent')} #{r.get('attempt')}] validity={fr.get('validity')} "
                  f"score={fr.get('score')} cases={len(cases)} PASS={len(passed)} FAIL={len(failed)}")
            if failed:
                print(f"      未通过: {failed}")


for n in ["qcpass-215", "qcpass2-217"]:
    show(n)
    print()
