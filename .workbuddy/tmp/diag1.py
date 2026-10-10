import pathlib, tomllib, zipfile, sys
sys.stdout.reconfigure(encoding="utf-8")
TD = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261006_fix6-150\FIN3-WKN-150")
d = tomllib.loads((TD/"tests"/"rubrics.toml").read_text(encoding="utf-8"))
print("TOML 顶层键:", list(d.keys()))
for k,v in d.items():
    print(f"  {k}: {type(v).__name__} len={len(v) if hasattr(v,'__len__') else '-'}")
    if isinstance(v, list) and v and isinstance(v[0], dict):
        print("     条目键:", list(v[0].keys()))
        print("     首条 id:", v[0].get("id"))
print()
z = zipfile.ZipFile(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261006_fix6-150.zip")
print("含 CRLF 的文件:")
for i in z.infolist():
    if i.is_dir(): continue
    if i.filename.endswith((".md",".toml",".json",".sh",".py")):
        b = z.read(i.filename)
        if b"\r\n" in b:
            print(f"   {i.filename}  ({i.file_size} B)")
