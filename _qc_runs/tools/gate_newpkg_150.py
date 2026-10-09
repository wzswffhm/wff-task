# -*- coding: utf-8 -*-
"""上传前门禁：验证新打的批次 zip 内部自洽（判据 == 判分快照）、文档无失实残留。"""
import json
import pathlib
import sys
import tomllib
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
ZP = H / "work_fin-b01_20261006_fix5-150.zip"
TOP = "work_fin-b01_20261006_fix5-150/FIN3-WKN-150/"
EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
ok = True


def chk(label, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(f"  [{'OK' if cond else '!!'}] {label}{('  ' + extra) if extra else ''}")


print("=" * 100)
print(f"新批次包：{ZP.name}  {ZP.stat().st_size:,} B")
print("=" * 100)
with zipfile.ZipFile(ZP) as zf:
    rub = tomllib.loads(zf.read(f"{TOP}tests/rubrics.toml").decode("utf-8"))["criterion"]
    rmap = {c["id"]: c["description"] for c in rub}
    jmap = {i["id"]: i for i in json.loads(zf.read(f"{TOP}rubrics.json").decode("utf-8"))["items"]}
    txt = zf.read(f"{TOP}tests/rubrics.toml").decode("utf-8")

    print("\n【质检 #2】判据 == 判分快照")
    for ex in EXEC:
        d = json.loads(zf.read(f"{TOP}跑分产物与轨迹/{ex}/reward-details.json").decode("utf-8"))["reward"]
        snap = {c["id"]: c["description"] for c in d["criteria"]}
        bad = [k for k in snap if snap[k] != rmap.get(k)]
        chk(f"{ex}", not bad, str(bad) if bad else "")
    chk("toml description == rubrics.json description",
        not [k for k in rmap if rmap[k] != jmap.get(k, {}).get("description")])

    print("\n【质检 #6】去「个别」")
    chk("rubrics.toml 无『个别』", "个别" not in txt)
    chk("rubrics.json 无『个别』",
        "个别" not in zf.read(f"{TOP}rubrics.json").decode("utf-8"))

    print("\n【收紧已撤销】")
    chk("无『量化拆解』", "量化拆解" not in txt)
    chk("无『跨期变化的量化幅度』", "跨期变化的量化幅度" not in txt)

    print("\n【质检 #4】金标八章")
    import re
    g = zf.read(f"{TOP}tests/__golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md").decode("utf-8")
    ch = re.findall(r"^##\s*([一二三四五六七八九十]+)、", g, re.M)
    chk("章节数 == 8", len(ch) == 8, str(ch))
    chk("无『九、』", "九、" not in g)
    g2 = zf.read(f"{TOP}solution/golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md").decode("utf-8")
    chk("两份 golden 逐字节一致", g == g2)

    print("\n【质检 #5】费用率趋势")
    chk("含『下降趋势』", "下降趋势" in g)
    chk("无『期间费用率…上升』", not re.search(r"期间费用率[^。]{0,20}上升", g))

    print("\n【质检 #8】交付文档无失实残留")
    doc = zf.read(f"{TOP}交付文档.md").decode("utf-8")
    for kw in ("锚点收紧", "满分锚点", "量化拆解", "第三轮调整", "tighten-r29r30"):
        chk(f"文档无『{kw}』", kw not in doc)
    chk("文档含『质检整改后判分重跑』", "质检整改后判分重跑" in doc)

    print("\n【版本与分数】")
    tt = zf.read(f"{TOP}task.toml").decode("utf-8")
    chk("task.toml version == 1.0.5", 'version = "1.0.5"' in tt)
    s = json.loads(zf.read(f"{TOP}跑分产物与轨迹/summary.json").decode("utf-8"))
    chk("summary.task_version == 1.0.5", s.get("task_version") == "1.0.5", str(s.get("task_version")))
    chk("summary.round 已更新", s.get("round") == "fix3(qc-remediation)+rejudge", str(s.get("round")))
    chk("summary.mean == 0.634848", abs(s.get("mean", 0) - 0.634848) < 1e-9, str(s.get("mean")))
    chk("gate_pass == True", s.get("gate_pass") is True)

    print("\n【结构】")
    names = zf.namelist()
    chk("第二层仅 FIN3-WKN-150",
        sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]}) == ["FIN3-WKN-150"])
    chk("无 _rejudge/__pycache__ 残留",
        not [n for n in names if "_rejudge" in n or "__pycache__" in n or n.endswith(".pyc")])
    chk("文件数 114", len([n for n in names if not n.endswith("/")]) == 114,
        str(len([n for n in names if not n.endswith("/")])))

print()
print("=" * 100)
print(f">>> {'上传前门禁全部通过，可以重传飞书' if ok else '存在问题，勿上传'}")
print("=" * 100)
sys.exit(0 if ok else 1)
