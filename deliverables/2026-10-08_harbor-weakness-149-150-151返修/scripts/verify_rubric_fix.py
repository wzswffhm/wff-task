"""Verify the QC repair landed correctly for FIN3-WKN-149/150/151."""
import json
import pathlib
import re
import tomllib

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASKS = ["FIN3-WKN-149", "FIN3-WKN-150", "FIN3-WKN-151"]
CHART_CRIT = {"FIN3-WKN-149"}

ok = True
for tid in TASKS:
    task_dir = REPO / "harbor-weakness" / tid
    data = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    paths = [a for a in data["artifacts"] if a.startswith("/app/output/")]
    charts = [p for p in paths if p.endswith(".png")]
    memo = [p for p in paths if p.endswith(".md")][0]
    dir_lit = f"`/app/output/{tid}_charts/`"
    bare_lit = "`/app/output/`"

    d = tomllib.loads((task_dir / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
    jd = json.loads((task_dir / "rubrics.json").read_text(encoding="utf-8"))
    toml_by = {c["id"]: c for c in d["criterion"]}
    json_by = {it["id"]: it for it in jd["items"]}

    print("=" * 92)
    print(f"### {tid}   criteria toml={len(d['criterion'])} json={len(jd['items'])}")

    for label, desc in (("toml", toml_by["R01"]["description"]), ("json", json_by["R01"]["description"])):
        tail = desc.split("Deliverables to inspect:", 1)[1]
        n_paths = len(re.findall(r"`/app/output/[^`]+`", tail))
        missing = [p for p in paths if p not in tail]
        print(f"  R01[{label}] paths_in_tail={n_paths} dir_as_entry={'YES' if dir_lit in tail or bare_lit in tail else 'no'} missing={missing}")
        if n_paths != 7 or missing or dir_lit in tail or bare_lit in tail:
            ok = False

    if tid in CHART_CRIT:
        for label, desc in (("toml", toml_by["R28"]["description"]), ("json", json_by["R28"]["description"])):
            tail = desc.split("Deliverables to inspect:", 1)[1]
            want3 = [c for c in charts if any(k in c for k in ("chart02", "chart04", "chart05"))]
            missing = [c for c in want3 if c not in tail]
            print(f"  R28[{label}] dir_as_entry={'YES' if dir_lit in tail else 'no'} missing={missing}")
            if missing or dir_lit in tail:
                ok = False

    # every criterion still carries an inspect list; ids/names/weights/types intact
    bad = [c["id"] for c in d["criterion"] if "Deliverables to inspect" not in c["description"]]
    name_ok = all(c.get("name") == c["id"] for c in d["criterion"])
    w_ok = all(c["weight"] in (3.0, 7.0, 10.0) for c in d["criterion"])
    likert_ok = all(c.get("points") == 5 for c in d["criterion"] if c["type"] == "likert")
    ids_match = [c["id"] for c in d["criterion"]] == [it["id"] for it in jd["items"]]
    print(f"  invariants: no_inspect_list={bad} name_eq_id={name_ok} weight_range={w_ok} "
          f"likert_points5={likert_ok} ids_match_json={ids_match}")
    if bad or not (name_ok and w_ok and likert_ok and ids_match):
        ok = False

print("\nRESULT:", "PASS" if ok else "FAIL")
