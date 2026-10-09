# -*- coding: utf-8 -*-
"""搜索所有可用的 rubrics.toml / rubrics.json 副本，定位"收紧前（质检整改后）"的判据。

判定标准：
  - 不含"个别"          -> 满足质检 #6
  - 不含"量化拆解"/"跨期变化的量化幅度" -> 收紧前
"""
import hashlib
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TARGETS = {"rubrics.toml", "rubrics.json"}
QUANT = ("量化拆解", "跨期变化的量化幅度")
BAD_WORD = "个别"

rows = []


def classify(name, data: bytes):
    try:
        t = data.decode("utf-8")
    except Exception:
        try:
            t = data.decode("utf-8-sig")
        except Exception:
            return None
    if name.endswith(".json"):
        import json
        try:
            d = json.loads(t)
            items = d.get("items", [])
            txt = json.dumps(items, ensure_ascii=False)
        except Exception:
            txt = t
    else:
        txt = t
    return {
        "sha": hashlib.sha256(data).hexdigest()[:16],
        "size": len(data),
        "quant": sum(txt.count(q) for q in QUANT),
        "bad": txt.count(BAD_WORD),
        "txt": txt,
    }


print("=" * 108)
print("A) 文件系统中的判据副本")
print("=" * 108)
for p in sorted(ROOT.rglob("*")):
    if p.is_file() and p.name in TARGETS and "_rejudge" not in p.parts:
        try:
            info = classify(p.name, p.read_bytes())
        except Exception as e:
            print(f"  ?? {p}  {e}")
            continue
        if info:
            rows.append((str(p), info))
            tag = "收紧前OK" if (info["quant"] == 0 and info["bad"] == 0) else (
                "收紧后" if info["quant"] > 0 else ("含个别" if info["bad"] else "?"))
            print(f"  {tag:<9} sha={info['sha']} q={info['quant']} 个别={info['bad']} {info['size']:>7,}B  {p}")

print()
print("=" * 108)
print("B) zip 包内的判据副本")
print("=" * 108)
zips = [p for p in ROOT.rglob("*.zip") if p.is_file()]
for zp in sorted(zips, key=lambda x: x.stat().st_size, reverse=True)[:14]:
    try:
        with zipfile.ZipFile(zp) as zf:
            for n in zf.namelist():
                if pathlib.PurePosixPath(n).name in TARGETS:
                    info = classify(pathlib.PurePosixPath(n).name, zf.read(n))
                    if info:
                        rows.append((f"{zp} :: {n}", info))
                        tag = "收紧前OK" if (info["quant"] == 0 and info["bad"] == 0) else (
                            "收紧后" if info["quant"] > 0 else ("含个别" if info["bad"] else "?"))
                        print(f"  {tag:<9} sha={info['sha']} q={info['quant']} 个别={info['bad']} {info['size']:>7,}B")
                        print(f"            {zp.name} :: {n}")
    except Exception as e:
        print(f"  ?? {zp.name}: {e}")

print()
print("=" * 108)
print("C) 可直接使用的「收紧前且无个别」副本")
print("=" * 108)
good = [(src, i) for src, i in rows if i["quant"] == 0 and i["bad"] == 0]
for src, i in good:
    print(f"  sha={i['sha']}  {i['size']:>7,}B  {src}")
print(f"  共 {len(good)} 个")
