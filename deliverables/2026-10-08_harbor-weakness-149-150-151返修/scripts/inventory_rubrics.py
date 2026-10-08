"""Inventory 'Deliverables to inspect' lists in rubrics.toml + rubrics.json for a task dir."""
import json
import pathlib
import re
import sys
import tomllib

task = pathlib.Path(sys.argv[1])
name = task.name

print("=" * 100)
print(f"### {name}")
print("=" * 100)

toml_path = task / "tests" / "rubrics.toml"
data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
crit = data["criterion"]
print(f"\n-- rubrics.toml: {len(crit)} criteria --")
for c in crit:
    desc = c["description"]
    m = re.search(r"Deliverables to inspect:\s*(.+?)\.?\s*$", desc)
    paths = m.group(1) if m else "<<MISSING>>"
    flags = []
    if paths != "<<MISSING>>":
        if re.search(r"`[^`]*/`\s*$", paths) or re.search(r"`/app/output/`", paths):
            flags.append("DIR-ONLY")
        if "charts/" in paths and ".png" not in paths:
            flags.append("DIR-AS-DELIVERABLE")
    flag = ("  <<< " + ",".join(flags)) if flags else ""
    print(f"  {c['id']:5s} type={c['type']:7s} w={c['weight']:<5} neg={str(c.get('negate', False)):5s} {paths}{flag}")

json_path = task / "rubrics.json"
if json_path.exists():
    jd = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"\n-- rubrics.json top-level keys: {list(jd.keys())} --")
    items = jd if isinstance(jd, list) else jd.get("criteria") or jd.get("rubrics") or []
    if not items:
        for k, v in jd.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items = v
                print(f"   (criteria list found under key {k!r})")
                break
    print(f"   {len(items)} entries")
    for c in items:
        if not isinstance(c, dict):
            continue
        desc = str(c.get("description", ""))
        m = re.search(r"Deliverables to inspect:\s*(.+?)\.?\s*$", desc)
        paths = m.group(1) if m else "<<none>>"
        flag = ""
        if "charts/" in paths and ".png" not in paths:
            flag = "  <<< DIR-AS-DELIVERABLE"
        print(f"  {str(c.get('id')):5s} w={c.get('weight')} neg={c.get('negate')} type={c.get('type')} | {paths}{flag}")
