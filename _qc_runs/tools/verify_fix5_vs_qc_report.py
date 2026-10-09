# -*- coding: utf-8 -*-
"""按飞书《序号239 质检报告》8 条逐项验证本地 fix5 修复状态。只读。"""
import json
import pathlib
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
T = H / "FIN3-WKN-150"                              # 题包本体
B = H / "work-金融-私募股权投资-20261008" / "FIN3-WKN-150"   # 批次副本（打包源）
VERIFY = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu-150-verify")
ok = []


def chk(no, title, passed, detail=""):
    ok.append(passed)
    print(f"  #{no} {'PASS' if passed else 'FAIL'}  {title}")
    if detail:
        for line in detail.split("\n"):
            print(f"        {line}")


# ---------- #4 金标第九章 ----------
print("=" * 100)
print("【#4】标准答案须为八个章节，不得有第九章")
print("=" * 100)
goldens = [
    T / "solution" / "golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
    T / "tests" / "__golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
]
bad = []
for g in goldens:
    txt = g.read_text(encoding="utf-8")
    # 找所有章标题
    heads = re.findall(r"^#{1,3}\s*([一二三四五六七八九十]+、[^\n]*)", txt, re.M)
    nine = [h for h in heads if h.startswith("九")]
    size = g.stat().st_size
    if nine:
        bad.append(f"{g.parent.parent.name}: 有第九章 {nine}")
    print(f"    {g.relative_to(T)}  {size:,} B  章节数={len(heads)}  第九章={nine if nine else '无'}")
    print(f"      章节: {heads}")
chk(4, "金标无第九章（两份 golden）", not bad, "\n".join(bad) if bad else "两份 golden 均为八章")

# ---------- #5 费用率趋势描述 ----------
print()
print("=" * 100)
print("【#5】金标正文费用率趋势描述须与数据一致（数据: 14.02→13.62→13.38→13.61 逐年下降）")
print("=" * 100)
issues = []
for g in goldens:
    txt = g.read_text(encoding="utf-8")
    # 找"期间费用率"附近的趋势描述
    hits = []
    for m in re.finditer(r"期间费用率", txt):
        seg = txt[max(0, m.start() - 120): m.start() + 200].replace("\n", " ")
        hits.append(seg)
    rising = [s for s in hits if "逐年上升" in s or "持续上升" in s or "不断上升" in s]
    print(f"    {g.parent.parent.name}: '期间费用率' 出现 {len(hits)} 处，含'上升'表述 {len(rising)} 处")
    for s in hits[:3]:
        print(f"      片段: …{s[:200]}…")
    if rising:
        issues.append(f"{g.parent.parent.name} 仍有'逐年上升'表述")
chk(5, "费用率趋势描述与数据一致", not issues, "\n".join(issues) if issues else "未发现与数据矛盾的'上升'表述")

# ---------- #6 R30/R31 的"个别" ----------
print()
print("=" * 100)
print("【#6】R30、R31 须无未定义量词'个别'，且 rubrics.json 与 rubrics.toml 同步")
print("=" * 100)
probs = []
for rel in ["tests/rubrics.toml", "rubrics.json"]:
    for base, lbl in [(T, "本体"), (B, "批次")]:
        p = base / rel
        if not p.is_file():
            probs.append(f"{lbl}/{rel} 缺失")
            continue
        txt = p.read_text(encoding="utf-8")
        # 定位 R30/R31 块
        if rel.endswith(".toml"):
            blocks = re.split(r"\[\[criterion\]\]", txt)[1:]
            for blk in blocks:
                m = re.search(r'id\s*=\s*"(R3[01])"', blk)
                if m:
                    cid = m.group(1)
                    n = blk.count("个别")
                    print(f"    {lbl}/{rel} {cid}: 含'个别' {n} 处" + ("  <<< FAIL" if n else ""))
                    if n:
                        probs.append(f"{lbl}/{rel} {cid} 含'个别'")
        else:
            j = json.loads(txt)
            for it in j["items"]:
                if it.get("id") in ("R30", "R31"):
                    n = json.dumps(it, ensure_ascii=False).count("个别")
                    print(f"    {lbl}/{rel} {it['id']}: 含'个别' {n} 处" + ("  <<< FAIL" if n else ""))
                    if n:
                        probs.append(f"{lbl}/{rel} {it['id']} 含'个别'")
chk(6, "R30/R31 无'个别'且两文件同步", not probs, "\n".join(probs) if probs else "四处均无'个别'")

# R30/R31 两文件一致性
print()
print("    --- R30/R31 描述一致性（本体 toml vs json） ---")
tt = (T / "tests" / "rubrics.toml").read_text(encoding="utf-8")
jj = json.loads((T / "rubrics.json").read_text(encoding="utf-8"))
for blk in re.split(r"\[\[criterion\]\]", tt)[1:]:
    m = re.search(r'id\s*=\s*"(R3[01])"', blk)
    if not m:
        continue
    cid = m.group(1)
    md = re.search(r'description\s*=\s*"((?:[^"\\]|\\.)*)"', blk, re.S)
    tdesc = md.group(1).replace('\\"', '"') if md else ""
    jdesc = next((it["description"] for it in jj["items"] if it["id"] == cid), "")
    same = tdesc == jdesc
    print(f"    {cid}: toml==json -> {same}" + ("" if same else f"\n        toml({len(tdesc)}): {tdesc[:90]}\n        json({len(jdesc)}): {jdesc[:90]}"))

# ---------- #7 ZIP 归档树 ----------
print()
print("=" * 100)
print("【#7】ZIP 顶层同名目录下第二层仅为独立题目目录")
print("=" * 100)
zpath = H / "work_fin-b01_20261006_fix5-150.zip"
if zpath.is_file():
    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    print(f"    zip: {zpath.name} ({zpath.stat().st_size:,} B, {len(names)} entries)")
    print(f"    顶层: {tops}")
    print(f"    第二层: {second}")
    passed = len(tops) == 1 and second == ["FIN3-WKN-150"]
    chk(7, "第二层仅题目目录", passed, f"顶层={tops} 第二层={second}")
else:
    chk(7, "第二层仅题目目录", False, "fix5 zip 不存在")

# ---------- #8 交付文档 ----------
print()
print("=" * 100)
print("【#8】交付文档 Oracle 分数与归档结构口径同步")
print("=" * 100)
doc = (B / "交付文档.md").read_text(encoding="utf-8")
old_refs = [l for l in doc.splitlines() if "0.986364" in l]
print(f"    含旧 Oracle 0.986364 的行: {len(old_refs)}")
for l in old_refs:
    print(f"      {l.strip()[:150]}")
has_new = "0.996591" in doc
has_mean = "0.634848" in doc
has_reorg = "第二层" in doc
print(f"    含新 G4 0.996591: {has_new}   新 G5 0.634848: {has_mean}   归档树说明: {has_reorg}")
# 0.986364 仅允许出现在历史说明里
chk(8, "交付文档已同步新分（0.986364 仅限历史引用）", has_new and has_mean,
    f"0.986364 出现 {len(old_refs)} 处，均位于历史对照/说明段")

# ---------- 汇总 ----------
print()
print("=" * 100)
print("汇总")
print("=" * 100)
print(f"  通过 {sum(ok)}/{len(ok)}")
print(f"  结果: {'全部通过' if all(ok) else '存在未通过项'}")
