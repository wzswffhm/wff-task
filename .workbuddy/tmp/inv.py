import pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = R/"harbor-weakness"
def sz(p):
    if p.is_file(): return p.stat().st_size
    t=0
    for f in p.rglob("*"):
        if f.is_file(): t+=f.stat().st_size
    return t
def mb(n): return f"{n/1048576:.1f} MB" if n>=1048576 else f"{n/1024:.0f} KB"
print("=== harbor-weakness 顶层目录 ===")
for p in sorted(H.iterdir()):
    if p.is_dir():
        cnt=sum(1 for f in p.rglob("*") if f.is_file())
        print(f"  {p.name:<44} {mb(sz(p)):>9}  {cnt:>5} 文件")
print("\n=== harbor-weakness 顶层文件 ===")
for p in sorted(H.iterdir()):
    if p.is_file():
        print(f"  {p.name:<44} {mb(sz(p)):>9}")
print("\n=== _qc_runs 顶层子项 ===")
q=H/"_qc_runs"
if q.is_dir():
    for p in sorted(q.iterdir()):
        print(f"  {p.name:<48} {mb(sz(p)):>9}  {'dir' if p.is_dir() else 'file'}")
    if not any(q.iterdir()): print("  (空)")
print("\n=== 全仓所有 .zip（排除 .git）===")
for p in sorted(R.rglob("*.zip")):
    if ".git" in p.parts: continue
    print(f"  {str(p.relative_to(R)):<70} {mb(p.stat().st_size):>9}")
