# -*- coding: utf-8 -*-
"""飞书 282 上传后终态复核。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

f = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu_282_final.json")
d = json.loads(f.read_text(encoding="utf-8-sig"))
m = d["data"]
rows = m["data"]
names = m["fields"]
i = names.index("序号")

CHECK = {
    "状态": "领取",
    "题目难度": "A2",
    "类型": "weakness",
}
ATTACH = {
    "交付物": ("work_fin-b01_20261009-152.zip", 4714450),
    "题目附件信息": ("FIN3-WKN-152_task.zip", 125357),
    "标准答案附件信息": ("FIN3-WKN-152_answer.zip", 199432),
}

allok = True
found = False
for r in rows:
    if str(r[i]) != "282":
        continue
    found = True
    print("=" * 84)
    print("飞书 序号 282 终态复核")
    print("=" * 84)

    for k, want in CHECK.items():
        j = names.index(k)
        v = r[j]
        got = v[0] if isinstance(v, list) and v else v
        ok = (got == want)
        allok &= ok
        print(f"  [{'OK' if ok else '!!'}] {k}: {got!r}  (期望 {want!r})")

    for k, (wname, wsize) in ATTACH.items():
        j = names.index(k)
        v = r[j]
        if not isinstance(v, list) or len(v) != 1:
            allok = False
            print(f"  [!!] {k}: {0 if not isinstance(v, list) else len(v)} 个文件（应恰好 1 个）")
            continue
        a = v[0]
        name_ok = a.get("name") == wname
        size_ok = a.get("size") == wsize
        ok = name_ok and size_ok
        allok &= ok
        print(f"  [{'OK' if ok else '!!'}] {k}: {a.get('name')}  {a.get('size'):,} B")
        print(f"         token={a.get('file_token')}")
        if not name_ok:
            print(f"         [!!] 文件名应为 {wname}")
        if not size_ok:
            print(f"         [!!] 大小应为 {wsize:,}")

    # 质检报告字段（不应被我动）
    j = names.index("质检报告")
    print(f"  [—] 质检报告: {r[j]}（未触碰）")
    break

if not found:
    print("  [!!] 未找到 282")
    allok = False

print()
print("=" * 84)
print(">>> " + ("282 终态全部符合预期（状态保持「领取」、难度 A2、三附件各 1 个）" if allok else "存在问题"))
print("=" * 84)
sys.exit(0 if allok else 1)
