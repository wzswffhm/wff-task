"""聚焦提取 QC 报告门禁结论：静态 + Oracle/NOP 动态轮次。"""
import json
import pathlib

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")

for name in ["qcorig-215", "qcorig-217", "qcpass-215", "qcpass-217", "qcpass2-217",
             "qcfinal-01", "full-04"]:
    p = Q / name / "report.json"
    if not p.is_file():
        print(f"## {name}: 无 report.json")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 88)
    print(f"## {name}   conclusion = {d.get('conclusion')}   ({d.get('generated_at')})")

    for t in d.get("tasks") or []:
        print(f"  task = {t.get('task_id')}")
        print(f"    static_pass = {t.get('static_pass')}")
        for e in (t.get("errors") or [])[:3]:
            print(f"    [ERROR] {str(e)[:190]}")
        for w in (t.get("warnings") or [])[:3]:
            print(f"    [WARN ] {str(w)[:190]}")
        rq = t.get("required_testcases") or []
        f2p = [x for x in rq if x.get("group") == "F2P"]
        p2p = [x for x in rq if x.get("group") == "P2P"]
        print(f"    required: 共{len(rq)} （F2P {len(f2p)} / P2P {len(p2p)}）")

    runs = d.get("runs") or []
    print(f"  runs: {len(runs)} 轮")
    for r in runs:
        keys = {k: r.get(k) for k in ("agent", "attempt", "validity", "score", "status",
                                       "verdict", "job", "cases_passed", "cases_total",
                                       "reward", "error") if k in r}
        print(f"    {json.dumps(keys, ensure_ascii=False)[:300]}")
    print()
