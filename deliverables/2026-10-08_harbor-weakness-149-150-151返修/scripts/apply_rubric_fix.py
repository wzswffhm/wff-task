"""Apply the QC repair for FIN3-WKN-149/150/151: enumerate mandatory deliverables.

Fix (149 F02 / 150 F01 / 151 F01):
  R01 "交付物齐全" previously ended with `Deliverables to inspect: `/app/output/`.`,
  i.e. a directory standing in for the 7 mandatory files (pitfall A6). It now lists
  every mandatory file path explicitly.
  For 149 only, R28 also pointed at the `FIN3-WKN-149_charts/` directory; it now lists
  the chart files it actually inspects.

The path list is derived from task.toml `artifacts` so it stays byte-identical with the
source of truth. Both the design-state rubrics.json and the runtime tests/rubrics.toml
are edited in lockstep (pitfall B11 / check_package #4b).
"""
import json
import pathlib
import shutil
import sys
import tomllib

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASKS = ["FIN3-WKN-149", "FIN3-WKN-150", "FIN3-WKN-151"]
BACKUP = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None

OLD_R01 = "Deliverables to inspect: `/app/output/`."
TASKS_WITH_CHART_CRIT = {"FIN3-WKN-149"}


def artifact_paths(task_dir: pathlib.Path) -> list[str]:
    data = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    return [
        a
        for a in data["artifacts"]
        if a.startswith("/app/output/") and not a.rstrip("/").endswith("output")
    ]


def render(paths: list[str]) -> str:
    return "Deliverables to inspect: " + ", ".join(f"`{p}`" for p in paths) + "."


for tid in TASKS:
    task_dir = REPO / "harbor-weakness" / tid
    paths = artifact_paths(task_dir)
    memo = [p for p in paths if p.endswith(".md")]
    repro = [p for p in paths if p.endswith(".py")]
    charts = [p for p in paths if p.endswith(".png")]
    assert len(paths) == 7 and len(memo) == 1 and len(repro) == 1 and len(charts) == 5, (
        tid,
        paths,
    )
    print(f"### {tid}: {len(paths)} mandatory files")

    for rel in ("tests/rubrics.toml", "rubrics.json"):
        fp = task_dir / rel
        if BACKUP is not None:
            dst = BACKUP / tid / rel.replace("/", "__")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fp, dst)

        lines = fp.read_text(encoding="utf-8").split("\n")
        hits = {"R01": 0, "R28": 0}
        for i, ln in enumerate(lines):
            if "交付物齐全：" in ln and OLD_R01 in ln:
                new_tail = render(paths)
                lines[i] = ln.replace(OLD_R01, new_tail)
                hits["R01"] += 1
            elif tid in TASKS_WITH_CHART_CRIT and "图表与正文数值一致：" in ln:
                old = (
                    "Deliverables to inspect: "
                    f"`/app/output/{tid}_charts/`, `{memo[0]}`."
                )
                if old in ln:
                    # R28 inspects chart02/chart04/chart05 -> name those three exactly.
                    want = [c for c in charts if any(k in c for k in ("chart02", "chart04", "chart05"))]
                    assert len(want) == 3, want
                    lines[i] = ln.replace(old, render(want + memo))
                    hits["R28"] += 1
        assert hits["R01"] == 1, (tid, rel, hits)
        if tid in TASKS_WITH_CHART_CRIT:
            assert hits["R28"] == 1, (tid, rel, hits)
        fp.write_text("\n".join(lines), encoding="utf-8")
        print(f"    {rel}: R01 rewritten" + (" + R28 rewritten" if hits["R28"] else ""))

print("\n--- verification ---")
for tid in TASKS:
    task_dir = REPO / "harbor-weakness" / tid
    paths = artifact_paths(task_dir)
    charts = [p for p in paths if p.endswith(".png")]

    d = tomllib.loads((task_dir / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
    jd = json.loads((task_dir / "rubrics.json").read_text(encoding="utf-8"))
    r01_t = next(c for c in d["criterion"] if c["id"] == "R01")
    r01_j = next(c for c in jd["items"] if c["id"] == "R01")

    for label, desc in (("toml R01", r01_t["description"]), ("json R01", r01_j["description"])):
        tail = desc.split("Deliverables to inspect:", 1)[1]
        assert f"/app/output/{tid}_charts/" not in tail, (tid, label, "charts dir in list")
        assert "`/app/output/`" not in tail, (tid, label, "bare output dir in list")
        assert tail.count("`/app/output/") == 7, (tid, label, tail.count("`/app/output/"))
        for c in charts:
            assert c in tail, (tid, label, c)
        assert all(p in tail for p in paths), (tid, label)
    print(f"  {tid}: R01 tail lists all 7 full paths, no bare directory  [toml+json OK]")

    if tid in TASKS_WITH_CHART_CRIT:
        r28_t = next(c for c in d["criterion"] if c["id"] == "R28")
        r28_j = next(c for c in jd["items"] if c["id"] == "R28")
        for label, desc in (("toml R28", r28_t["description"]), ("json R28", r28_j["description"])):
            tail = desc.split("Deliverables to inspect:", 1)[1]
            assert f"/app/output/{tid}_charts/`" not in tail, (tid, label, "charts dir in list")
            for c in charts:
                if any(k in c for k in ("chart02", "chart04", "chart05")):
                    assert c in tail, (tid, label, c)
        print(f"  {tid}: R28 tail names chart02/04/05 paths, no charts directory")

    # structural invariants unchanged
    assert len(d["criterion"]) == len(jd["items"])
    print(f"  {tid}: criteria counts toml={len(d['criterion'])} json={len(jd['items'])} (unchanged)")
