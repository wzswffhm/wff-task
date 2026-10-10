import hashlib, pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
a = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\tmp\feishu_dl\复检报告_飞书版.md")
b = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\tmp\dl239\序号239_20261009复检报告.md")
ha, hb = hashlib.sha256(a.read_bytes()).hexdigest(), hashlib.sha256(b.read_bytes()).hexdigest()
print(f"  飞书版: {a.stat().st_size} B  sha={ha[:16]}")
print(f"  本地版: {b.stat().st_size} B  sha={hb[:16]}")
print(f"  一致: {ha == hb}")
