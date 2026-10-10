import pathlib, sys, hashlib
sys.stdout.reconfigure(encoding="utf-8")
REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
MD = "FIN3-WKN-150_PreIPO投资决策备忘录.md"
pairs = [("solution/golden_output", REPO/"harbor-weakness"/"FIN3-WKN-150"/"solution"/"golden_output"),
         ("tests/__golden_output", REPO/"harbor-weakness"/"FIN3-WKN-150"/"tests"/"__golden_output"),
         ("批次目录", REPO/"harbor-weakness"/"work_fin-b01_20261006_fix6-150"/"FIN3-WKN-150"/"solution"/"golden_output")]
for tag, d in pairs:
    p = d/MD
    t = p.read_text(encoding="utf-8")
    print(f'  {tag:22} 存在={p.is_file()} 含"加：非经常性损益（税后）"={"加：非经常性损益（税后）" in t} sha={hashlib.sha256(p.read_bytes()).hexdigest()[:16]}')
