import json, pathlib, sys
root = pathlib.Path(sys.argv[1]) / "runs" / "wfflab__wreparse-217"
rows = []
for d in sorted(root.iterdir()):
    if not d.is_dir() or not d.name.startswith("20261005T19") and not d.name.startswith("20261005T20") and not d.name.startswith("20261005T21"):
        continue
    for sub in d.iterdir():
        rj = sub / "result.json"
        if not rj.exists():
            continue
        data = json.loads(rj.read_text(encoding="utf-8-sig"))
        rep = (data.get("test") or {}).get("report") or {}
        agent = data.get("agent") or {}
        rows.append((d.name, data.get("model_alias"), data.get("verdict"), rep.get("status"),
                     rep.get("score"), agent.get("status"), agent.get("turns"),
                     (agent.get("error") or "")[:120]))
for r in rows:
    print(" | ".join(str(x) for x in r))
print("total:", len(rows))
