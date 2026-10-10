import pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
ARC = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹")
targets = [ARC/"summary.json"] + [ARC/e/"reward.json" for e in ("oracle","qwen3.8-max-0902","claude-opus-4-8","gpt-5.6-sol")]
for p in targets:
    b = p.read_bytes()
    if b"\r\n" in b:
        nb = b.replace(b"\r\n", b"\n")
        p.write_bytes(nb)
        print(f"  修复 CRLF -> LF: {p.parent.name}/{p.name}  {len(b)} -> {len(nb)} B")
    else:
        print(f"  已是 LF: {p.parent.name}/{p.name}")
