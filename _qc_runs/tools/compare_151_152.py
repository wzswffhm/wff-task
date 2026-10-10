# -*- coding: utf-8 -*-
"""解剖 151（序号267，一审通过）交付包的目录结构与文档章法，作为 152 的对照基准。"""
import json
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
Z151 = H / "work_fin-b01_20261006-151.zip"
Z152 = H / "_qc_runs" / "packages" / "work_fin-b01_20261009-152.zip"

for tag, zp in (("151(对照/一审通过)", Z151), ("152(待交付)", Z152)):
    if not zp.exists():
        print(f"[缺] {zp}"); continue
    print("=" * 100)
    print(f"{tag}  {zp.name}  {zp.stat().st_size:,} B")
    print("=" * 100)
    with zipfile.ZipFile(zp) as zf:
        infos = zf.infolist()
        names = [i.filename for i in infos]
        files = [n for n in names if not n.endswith("/")]
        tops = sorted({n.split("/")[0] for n in names})
        seconds = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
        print(f"  entries={len(names)} (文件 {len(files)})  顶层={tops}  第二层={seconds}")
        # 权限
        perm = {}
        for i in infos:
            if i.filename.endswith(("solve.sh", "test.sh")):
                perm[i.filename] = oct((i.external_attr >> 16) & 0o777)
        print(f"  0755 检查: {perm}")
        # 跑分产物位置与构成
        runs = [n for n in files if "跑分产物" in n]
        print(f"  跑分产物条目 {len(runs)} 个:")
        dirs = sorted({n.split("跑分产物与轨迹/")[1].split("/")[0]
                       for n in runs if "跑分产物与轨迹/" in n and len(n.split("跑分产物与轨迹/")[1].split("/")) > 1})
        print(f"    执行体目录: {dirs}")
        sj = [n for n in runs if n.endswith("summary.json")]
        if sj:
            j = json.loads(zf.read(sj[0]).decode("utf-8"))
            print(f"    summary 字段: {list(j.keys())}")
            for k in ("task_version", "round", "three_model_mean", "measured_band",
                      "declared_difficulty", "gate_pass", "oracle_reward", "blocker"):
                if k in j:
                    print(f"      {k} = {j[k]}")
        # 交付文档章节
        docs = [n for n in files if n.endswith("交付文档.md")]
        if docs:
            d = zf.read(docs[0]).decode("utf-8", errors="replace")
            heads = [l.strip() for l in d.splitlines() if l.startswith("#")]
            print(f"  交付文档: {docs[0]}  {len(d.splitlines())} 行")
            for h in heads[:40]:
                print(f"    {h[:100]}")
        # 关键文件是否齐
        need = ["instruction.md", "task.toml", "rubrics.json",
                "environment/Dockerfile", "solution/solve.sh",
                "tests/test.sh", "tests/finalize.py", "tests/prompt.md", "tests/rubrics.toml"]
        miss = [k for k in need if not any(n.endswith("/" + k) or n.endswith(k) for n in files)]
        print(f"  五件套关键文件缺失: {miss if miss else '无 ✓'}")
        # 残留/禁入
        bad = [n for n in files if "_rejudge" in n or "__pycache__" in n
               or n.endswith(".pyc") or "reward-details-graded" in n]
        print(f"  禁入项: {bad if bad else '无 ✓'}")
        # input_files 计数
        inp = [n for n in files if "/environment/input_files/" in n]
        print(f"  input_files: {len(inp)} 个")
        print()
