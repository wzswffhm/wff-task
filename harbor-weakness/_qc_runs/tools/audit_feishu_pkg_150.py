# -*- coding: utf-8 -*-
"""审计飞书当前交付包（序号239）：
  1) 四场判分产物的生成时间（zip 条目时间戳）
  2) 包内 tests/rubrics.toml 的 R29/R30（收紧版？）
  3) 包内 reward-details.json 的 R29/R30 快照（收紧前？）-> 是否自相矛盾
  4) 逐条对照质检报告 8 项
"""
import json
import pathlib
import sys
import tomllib
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

ZP = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu-150-verify\verify_fix5_dlv.zip")
TOP = "work_fin-b01_20261006_fix5-150/FIN3-WKN-150/"
EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

print("=" * 104)
print(f"飞书交付包：{ZP.name}  {ZP.stat().st_size:,} B")
print("=" * 104)

with zipfile.ZipFile(ZP) as zf:
    infos = {i.filename: i for i in zf.infolist()}

    print()
    print("【1】四场判分产物的生成时间（zip 条目时间戳 = 打包取用的文件时间）")
    print("-" * 104)
    for ex in EXEC:
        for fn in ("reward.json", "reward-details.json"):
            n = f"{TOP}跑分产物与轨迹/{ex}/{fn}"
            if n in infos:
                dt = infos[n].date_time
                d = json.loads(zf.read(n).decode("utf-8"))
                val = d.get("reward") if fn == "reward.json" else d.get("reward", {}).get("score")
                print(f"  {ex:<18} {fn:<22} {dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d} {dt[3]:02d}:{dt[4]:02d}  score={val}")
    for fn in ("summary.json",):
        n = f"{TOP}跑分产物与轨迹/{fn}"
        if n in infos:
            dt = infos[n].date_time
            print(f"  {'':<18} {fn:<22} {dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d} {dt[3]:02d}:{dt[4]:02d}")

    print()
    print("【2】包内 tests/rubrics.toml 的 R29 / R30")
    print("-" * 104)
    rub = tomllib.loads(zf.read(f"{TOP}tests/rubrics.toml").decode("utf-8"))["criterion"]
    rmap = {c["id"]: c["description"] for c in rub}
    for k in ("R29", "R30"):
        d = rmap[k]
        print(f"  {k}: 含'量化拆解'={'量化拆解' in d}  含'跨期变化的量化幅度'={'跨期变化的量化幅度' in d}  含'个别'={'个别' in d}")
    print(f"  全文含'个别'={'个别' in zf.read(f'{TOP}tests/rubrics.toml').decode('utf-8')}")

    print()
    print("【3】包内判分快照（reward-details.json）的 R29 / R30 —— 与上面比对")
    print("-" * 104)
    for ex in ("oracle",):
        d = json.loads(zf.read(f"{TOP}跑分产物与轨迹/{ex}/reward-details.json").decode("utf-8"))["reward"]
        snap = {c["id"]: c["description"] for c in d["criteria"]}
        for k in ("R29", "R30"):
            s = snap[k]
            print(f"  {ex} {k}: 含'量化拆解'={'量化拆解' in s}  含'跨期变化的量化幅度'={'跨期变化的量化幅度' in s}")
        diff = [k for k in snap if snap[k] != rmap.get(k)]
        print(f"  >>> 判分快照 与 tests/rubrics.toml 不一致的条目: {diff if diff else '无'}")
        print(f"  >>> 质检 #2（36 条判据描述与 rubrics.toml 一致）当前成立? {not diff}")

    print()
    print("【4】包内打分与版本")
    print("-" * 104)
    tt = zf.read(f"{TOP}task.toml").decode("utf-8")
    for line in tt.splitlines():
        if line.strip().startswith(("version", "difficulty", "task_id", "name")):
            print(f"  task.toml: {line.strip()}")
    s = json.loads(zf.read(f"{TOP}跑分产物与轨迹/summary.json").decode("utf-8"))
    print(f"  summary: task_version={s.get('task_version')}  mean={s.get('mean')}  gate_pass={s.get('gate_pass')}")
    print(f"           declared_difficulty={s.get('declared_difficulty')}  round={s.get('round')}")

    print()
    print("【5】交付文档里的关键表述")
    print("-" * 104)
    doc = zf.read(f"{TOP}交付文档.md").decode("utf-8")
    for i, line in enumerate(doc.splitlines(), 1):
        if any(k in line for k in ("收紧", "regrade", "0.996591", "0.634848", "锚点")):
            print(f"  L{i}: {line.strip()[:150]}")

    print()
    print("【6】金标（质检 #4 八章 / #5 费用率）")
    print("-" * 104)
    g = zf.read(f"{TOP}tests/__golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md").decode("utf-8")
    import re
    chapters = re.findall(r"^##\s*([一二三四五六七八九十]+)、", g, re.M)
    print(f"  章节数={len(chapters)}  章={chapters}")
    print(f"  含'九、'={'九、' in g}")
    print(f"  含'逐年上升'={'逐年上升' in g}   含'下降趋势'={'下降趋势' in g}")
    print(f"  含'14.02'={'14.02' in g}  含'13.38'={'13.38' in g}  含'13.61'={'13.61' in g}")
