# -*- coding: utf-8 -*-
"""核验「飞书上真实附件」是否已包含序号 239 复检报告要求的全部修复。

数据来源全部是 `lark base +record-download-attachment` 从飞书下载回来的 zip
（.workbuddy/tmp/feishu_dl/），配合飞书下载的质检报告原件，不依赖本地工作副本。
"""
import hashlib
import json
import pathlib
import re
import sys
import tomllib
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
DL = REPO / ".workbuddy" / "tmp" / "feishu_dl"
LOCAL = REPO / "harbor-weakness"
BATCH = DL / "batch.zip"
TASK = DL / "task.zip"
ANS = DL / "answer.zip"
REPORT = DL / "复检报告_飞书版.md"
PREFIX = "work_fin-b01_20261006_fix6-150/FIN3-WKN-150/"
MD = "FIN3-WKN-150_PreIPO投资决策备忘录.md"

# 飞书记录实测值（record-list 取得）
FEISHU = {"batch": 14068377, "task": 68668, "answer": 928842, "report": 2527}

rows, bad = [], 0


def ck(item, ok, detail=""):
    global bad
    if not ok:
        bad += 1
    rows.append(("OK" if ok else "!!", item, detail))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------- 0. 落地校验：飞书附件 == 本地最新产物 ----------
ck("飞书交付包大小 = 飞书记录值", BATCH.stat().st_size == FEISHU["batch"],
   f"{BATCH.stat().st_size:,} B")
ck("飞书题目包大小 = 飞书记录值", TASK.stat().st_size == FEISHU["task"], f"{TASK.stat().st_size:,} B")
ck("飞书答案包大小 = 飞书记录值", ANS.stat().st_size == FEISHU["answer"], f"{ANS.stat().st_size:,} B")
ck("飞书交付包 sha256 == 本地最新打包",
   sha(BATCH) == sha(LOCAL / "work_fin-b01_20261006_fix6-150.zip"), sha(BATCH)[:16])
ck("飞书题目包 sha256 == 本地最新打包",
   sha(TASK) == sha(LOCAL / "FIN3-WKN-150_task.zip"), sha(TASK)[:16])
ck("飞书答案包 sha256 == 本地最新打包",
   sha(ANS) == sha(LOCAL / "FIN3-WKN-150_answer.zip"), sha(ANS)[:16])
ck("飞书质检报告 == 报告原件（sha 一致）",
   sha(REPORT) == sha(REPO / ".workbuddy" / "tmp" / "dl239" / "序号239_20261009复检报告.md"),
   sha(REPORT)[:16])

# ---------- 1. 报告第 4 条：利润桥闭合（在飞书包内金标上验） ----------
bz = zipfile.ZipFile(BATCH)
infos = {i.filename: i for i in bz.infolist()}
names = set(infos)
for sub, tag in ((f"{PREFIX}solution/golden_output", "solution/golden_output"),
                 (f"{PREFIX}tests/__golden_output", "tests/__golden_output"),
                 (f"{PREFIX}跑分产物与轨迹/oracle/output", "oracle/output")):
    md = bz.read(f"{sub}/{MD}").decode("utf-8")
    m = re.search(r"\|\s*加：非经常性损益（税后）\s*\|\s*([\d,]+)\s*\|", md)
    vals = [int(v.replace(",", "")) for v in
            re.findall(r"\|\s*加：[^|]*\|\s*([\d,]+)\s*\|", md)]
    ck(f"第4条 飞书包内 {tag} 桥接表含「加回非经常性损益」", bool(m),
       f"金额={m.group(1) if m else '未找到'}")
    ck(f"第4条 飞书包内 {tag} 桥接闭合 = 24,740", 12070 + sum(vals) == 24740,
       f"12,070+{sum(vals):,}={12070 + sum(vals):,}")
    ck(f"第4条 飞书包内 {tag} 保留 24,740 且无 22,190",
       "24,740" in md and "22,190" not in md)
    ck(f"第4条 飞书包内 {tag} 备忘录 sha == 本地金标",
       hashlib.sha256(md.encode("utf-8")).hexdigest()[:16] ==
       hashlib.sha256((LOCAL / "FIN3-WKN-150" / ("solution/golden_output" if "solution" in sub
                                                 else "tests/__golden_output" if "tests" in sub
                                                 else "solution/golden_output") / MD)
                      .read_bytes()).hexdigest()[:16]
       if "oracle" not in sub else True,
       hashlib.sha256(md.encode("utf-8")).hexdigest()[:16])

# 三份副本互比
md1 = bz.read(f"{PREFIX}solution/golden_output/{MD}")
md2 = bz.read(f"{PREFIX}tests/__golden_output/{MD}")
md3 = bz.read(f"{PREFIX}跑分产物与轨迹/oracle/output/{MD}")
ck("第4条 飞书包内三份金标备忘录逐字节一致", md1 == md2 == md3,
   f"sha={hashlib.sha256(md1).hexdigest()[:16]}")

# ---------- 2. 报告第 5 条：权限 0755 / LF / 结构 ----------
for fp, tag in ((BATCH, "交付包"), (TASK, "题目包"), (ANS, "答案包")):
    with zipfile.ZipFile(fp) as z:
        shs = {i.filename.split("/")[-1]: ((i.external_attr >> 16) & 0o777)
               for i in z.infolist() if i.filename.endswith(".sh")}
    ck(f"第5条 飞书{tag} 全部 .sh = 0755", all(v == 0o755 for v in shs.values()), str(shs))
with zipfile.ZipFile(BATCH) as z:
    others = {((i.external_attr >> 16) & 0o777) for i in z.infolist()
              if not i.is_dir() and not i.filename.endswith(".sh")}
    crlf = [n for n in z.namelist()
            if n.endswith((".md", ".toml", ".json", ".sh", ".py")) and b"\r\n" in z.read(n)]
    ns = z.namelist()
ck("第5条 飞书交付包非 .sh 文件统一 0644", others == {0o644}, str([oct(o) for o in others]))
ck("第5条 飞书交付包无 CRLF（保持 LF）", not crlf, f"CRLF={len(crlf)}")
ck("第5条 飞书交付包无重复前缀 / 第二层唯一",
   (not any(n.startswith(f"{PREFIX}{PREFIX}") for n in ns))
   and all(n.split("/")[1] == "FIN3-WKN-150" for n in ns if n.count("/") >= 1 and n.split("/")[1]))

# ---------- 3. 报告第 6 条：文档口径统一（在飞书包内文档上验） ----------
doc = bz.read(f"{PREFIX}交付文档.md").decode("utf-8")
ck("第6条 飞书包内交付文档含 §9.1 判据版本变更史", "### 9.1 判据版本变更史" in doc)
ck("第6条 飞书包内交付文档含 §10 第四轮记录", "## 10. 第四轮整改记录" in doc)
ck("第6条 飞书包内文档已无自相矛盾表述",
   "与上一轮**完全一致、未作任何修改**" not in doc and "有（限定 2 条）" in doc)

# ---------- 4. 报告第 1/2/7 条 + 返修要求：判据与分数 ----------
rt = tomllib.loads(bz.read(f"{PREFIX}tests/rubrics.toml").decode("utf-8"))
rj = json.loads(bz.read(f"{PREFIX}rubrics.json").decode("utf-8"))
ck("第1条 飞书交付包 rubrics.toml 判据 36 条", len(rt.get("criterion") or []) == 36,
   f"{len(rt.get('criterion') or [])}")
ck("第1条 飞书交付包 rubrics.json 判据 36 条", len(rj.get("items") or []) == 36,
   f"{len(rj.get('items') or [])}")
ck("第1条 双文件 description 逐字一致",
   {i["id"]: i["description"] for i in rt["criterion"]}
   == {i["id"]: i["description"] for i in rj["items"]})
ck("第1条 S_max = 220",
   (rj.get("metadata") or {}).get("scoring", {}).get("s_max") == 220)

sc = json.loads(bz.read(f"{PREFIX}跑分产物与轨迹/summary.json").decode("utf-8"))
want = {"oracle": 1.0, "qwen3.8-max-0902": 0.765909,
        "claude-opus-4-8": 0.573864, "gpt-5.6-sol": 0.654545}
got = {r["model"]: r["reward"] for r in sc["runs"]}
ck("第2条 飞书交付包 summary 四执行体分数 = 本轮重跑值", got == want, str(got))
ck("第2条 飞书交付包 summary mean=0.664773 / gate_pass / A1",
   sc["mean"] == 0.664773 and sc["gate_pass"] is True and sc["declared_difficulty"] == "A1",
   f"mean={sc['mean']} gate={sc['gate_pass']} 难度={sc['declared_difficulty']}")
ck("返修 飞书交付包 summary task_version=1.0.6 且 round 为本轮",
   sc["task_version"] == "1.0.6" and sc["round"] == "fix6(qc3-remediation)+rejudge",
   f"{sc['task_version']} / {sc['round']}")
for ex in want:
    r = json.loads(bz.read(f"{PREFIX}跑分产物与轨迹/{ex}/reward.json").decode("utf-8"))
    ck(f"返修 飞书交付包 {ex} reward/counted/err 正确",
       r["reward"] == want[ex] and r["criteria_counted"] == 36 and r["verifier_error"] == 0,
       f"reward={r['reward']} counted={r['criteria_counted']} err={r['verifier_error']}")

# ---------- 5. 报告第 3 条：PNG 留在子目录 ----------
for sub, tag in ((f"{PREFIX}solution/golden_output", "golden"),
                 (f"{PREFIX}跑分产物与轨迹/oracle/output", "oracle")):
    pngs = [n for n in names if n.startswith(f"{sub}/FIN3-WKN-150_charts/") and n.endswith(".png")]
    stray = [n for n in names if n.startswith(f"{sub}/") and n.endswith(".png")
             and "/FIN3-WKN-150_charts/" not in n]
    ck(f"第3条 飞书交付包 {tag} 五张 PNG 在 FIN3-WKN-150_charts/、根目录无散落",
       len(pngs) == 5 and not stray, f"子目录={len(pngs)} 散落={len(stray)}")

# ---------- 6. 附件包完整性 ----------
with zipfile.ZipFile(TASK) as z:
    tn = z.namelist()
    ck("题目包含 instruction.md / task.toml / environment / tests 四件",
       all(any(n.startswith(p) for n in tn) for p in
           ("FIN3-WKN-150/instruction.md", "FIN3-WKN-150/task.toml",
            "FIN3-WKN-150/environment/", "FIN3-WKN-150/tests/")), f"{len(tn)} 条目")
    ck("题目包不含金标（solution/__golden_output）",
       not any("golden_output" in n for n in tn))
with zipfile.ZipFile(ANS) as z:
    an = z.namelist()
    for p, cnt in (("FIN3-WKN-150/solution/golden_output/", 7),
                   ("FIN3-WKN-150/tests/__golden_output/", 7)):
        got_n = len([n for n in an if n.startswith(p) and not n.endswith("/")])
        ck(f"答案包 {p.split('/')[-2]} 含 {cnt} 个文件", got_n == cnt, f"实际={got_n}")
ck("飞书交付包无 _rejudge / 缓存残留",
   not any("_rejudge" in n or "__pycache__" in n or ".pytest_cache" in n for n in ns))

print(f"{'':2} {'检查项（数据源：飞书下载的附件）':<58} 说明")
print("-" * 120)
for flag, item, detail in rows:
    print(f"{flag:2} {item:<58} {detail}")
print("-" * 120)
print(f"共 {len(rows)} 项，未通过 {bad} 项 → "
      f"{'飞书交付包已确认修复完成 ✅' if bad == 0 else '存在未修复项 ❌'}")
sys.exit(1 if bad else 0)
