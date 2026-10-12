"""汇总参考包 jobs/ 的构成（每个 trial 的 agent 文件与判分读数）。"""
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
rows = []
for d in sorted(p for p in root.iterdir() if p.is_dir()):
    ag = d / "agent"
    vf = d / "verifier"
    agf = sorted(p.name for p in ag.iterdir()) if ag.is_dir() else []
    reward = (vf / "reward.txt").read_text(encoding="utf-8-sig").strip() if (vf / "reward.txt").is_file() else "-"
    status = ""
    res = vf / "result.json"
    if res.is_file():
        try:
            j = json.loads(res.read_text(encoding="utf-8-sig"))
            status = f"{j.get('status')} score={j.get('score')}"
        except Exception as exc:  # noqa: BLE001
            status = f"err {exc}"
    meta = ""
    if (d / "result.json").is_file():
        try:
            r = json.loads((d / "result.json").read_text(encoding="utf-8-sig"))
            md = ((r.get("agent_result") or {}).get("metadata") or {})
            meta = f"{md.get('alias')}/{md.get('model')}"
        except Exception:  # noqa: BLE001
            pass
    rows.append((d.name, reward, status, meta, ",".join(agf)))
    print(f"{d.name:<18} reward={reward:<4} {status:<15} {meta:<16} agent={','.join(agf)}")
print("total trials:", len(rows))
