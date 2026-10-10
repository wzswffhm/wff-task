import hashlib, pathlib, sys, tomllib
sys.stdout.reconfigure(encoding="utf-8")
H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
print("=== wff 题包目录存活确认 ===")
for t in ("FIN3-WKN-149","FIN3-WKN-150","FIN3-WKN-151","work-282-reddit-ipo"):
    p = H/t
    n = sum(1 for f in p.rglob("*") if f.is_file())
    need = ["instruction.md","task.toml","rubrics.json","environment","solution","tests"]
    ok = all((p/x).exists() for x in need) if t.startswith("FIN3") else p.is_dir()
    print(f"  {t:<22} {'✔' if ok else '✘'}  {n:>4} 文件  {'五件套齐全' if ok and t.startswith('FIN3') else ''}")
md = (H/"FIN3-WKN-150"/"solution"/"golden_output"/"FIN3-WKN-150_PreIPO投资决策备忘录.md").read_text(encoding="utf-8")
print(f"\n=== FIN3-WKN-150 题包关键内容 ===")
print(f"  金标含「加：非经常性损益（税后）」= {'加：非经常性损益（税后）' in md}")
print(f"  24,740 保留 = {'24,740' in md}；无 22,190 = {'22,190' not in md}")
t = tomllib.loads((H/"FIN3-WKN-150"/"task.toml").read_text(encoding="utf-8"))
print(f"  task.toml version = {t['task']['version']}；difficulty = {t['metadata'].get('difficulty')}")
r = (H/"FIN3-WKN-150"/"tests"/"rubrics.toml").read_text(encoding="utf-8")
print(f"  rubrics.toml 判据数 = {len(tomllib.loads(r).get('criterion') or [])}")
