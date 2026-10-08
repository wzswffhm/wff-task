"""Show rubrics.json deliverables_inspected + selected items + chart-related toml criteria."""
import json
import pathlib
import re
import sys
import tomllib

task = pathlib.Path(sys.argv[1])
jd = json.loads((task / "rubrics.json").read_text(encoding="utf-8"))
print("###", task.name)
print("deliverables_inspected =", json.dumps(jd.get("deliverables_inspected"), ensure_ascii=False, indent=2))
print("metadata =", json.dumps(jd.get("metadata"), ensure_ascii=False))
print()
for it in jd["items"]:
    if it.get("id") in ("R01", "R28"):
        print("--- json item", it["id"], "---")
        print(json.dumps(it, ensure_ascii=False, indent=2)[:2500])
        print()

d = tomllib.loads((task / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
print("--- toml criteria whose description mentions 图/chart ---")
for c in d["criterion"]:
    if re.search(r"图|chart", c["description"]):
        print(f"  {c['id']} w={c['weight']} :: {c['description'][:110]}...")
