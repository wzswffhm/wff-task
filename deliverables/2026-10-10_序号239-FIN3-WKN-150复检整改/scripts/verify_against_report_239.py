# -*- coding: utf-8 -*-
"""按甲方复检报告（序号 239，2026-10-09）逐条实测核验 FIN3-WKN-150 / fix6 成品。

报告 7 条：第 4/5/6 条【待改】必须闭环；第 1/2/3/7 条【正确】不得被破坏。
本脚本只读，全部结论来自实际读取文件/zip 字节。
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
H = REPO / "harbor-weakness"
BATCH_DIR = H / "work_fin-b01_20261006_fix6-150"
TD = BATCH_DIR / "FIN3-WKN-150"
ARC = TD / "跑分产物与轨迹"
BATCH_ZIP = H / "work_fin-b01_20261006_fix6-150.zip"
TASK_ZIP = H / "FIN3-WKN-150_task.zip"
ANS_ZIP = H / "FIN3-WKN-150_answer.zip"

MD = "FIN3-WKN-150_PreIPO投资决策备忘录.md"
rows, bad = [], 0


def ck(item, ok, detail=""):
    global bad
    if not ok:
        bad += 1
    rows.append(("OK" if ok else "!!", item, detail))


# ---------- 第 4 条：标准答案第四节利润桥闭合 ----------
COPIES = [TD / "solution" / "golden_output", TD / "tests" / "__golden_output", ARC / "oracle" / "output"]
texts, hashes = {}, {}
for c in COPIES:
    p = c / MD
    t = p.read_text(encoding="utf-8")
    texts[c.name if c.name != "output" else "oracle/output"] = t
    hashes[str(c.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]

a, b, c = texts["golden_output"], texts["__golden_output"], texts["oracle/output"]
ck("第4条 三份金标备忘录逐字节一致", a == b == c,
   f"sha={list(hashes.values())}")

bridge = re.search(r"\|\s*加：非经常性损益（税后）\s*\|\s*([\d,]+)\s*\|", a)
ck("第4条 桥接表含「加：非经常性损益（税后）」行", bool(bridge),
   f"金额={bridge.group(1) if bridge else '未找到'}")

vals = re.findall(r"\|\s*加：[^|]*\|\s*([\d,]+)\s*\|", a)
nums = [int(v.replace(",", "")) for v in vals]
kf = 12070
total = kf + sum(nums)
ck("第4条 桥接算术闭合（12,070＋各加项＝24,740）", total == 24740,
   f"加项={nums} 合计={total}")
ck("第4条 最终值 24,740 未被改为 22,190", "24,740" in a and "22,190" not in a,
   f"含24,740={'24,740' in a} 含22,190={'22,190' in a}")

# 桥接过程逐项与判据 R12 一致
for label, kw in [("所得税费用", "加：所得税费用"), ("利息费用", "加：利息费用"),
                  ("折旧与摊销", "加：折旧与摊销"), ("股份支付", "加：股份支付")]:
    ck(f"第4条 桥接表列出「{label}」", kw in a)

# 瀑布图同步（9 根柱）
py = (TD / "solution" / "golden_output" / "FIN3-WKN-150_reproduce.py").read_text(encoding="utf-8")
ck("第4条 瀑布图 steps 含「＋非经常性损益」", "＋非经常性损益" in py)

# ---------- 第 5 条：包内 .sh 权限 0755 ----------
for zp, rel in ((BATCH_ZIP, f"{BATCH_DIR.name}/FIN3-WKN-150/solution/solve.sh"),
                (BATCH_ZIP, f"{BATCH_DIR.name}/FIN3-WKN-150/tests/test.sh"),
                (TASK_ZIP, "FIN3-WKN-150/tests/test.sh"),
                (ANS_ZIP, "FIN3-WKN-150/solution/solve.sh")):
    with zipfile.ZipFile(zp) as z:
        infos = {i.filename: i for i in z.infolist()}
        mode = (infos[rel].external_attr >> 16) & 0o777
    ck(f"第5条 {zp.name} :: {rel.split('/')[-1]} 权限", mode == 0o755, oct(mode))

with zipfile.ZipFile(BATCH_ZIP) as z:
    names = set(z.namelist())
    others = {((i.external_attr >> 16) & 0o777) for i in z.infolist()
              if not i.is_dir() and not i.filename.endswith(".sh")}
    crlf = [n for n in names
            if n.endswith((".md", ".toml", ".json", ".sh", ".py")) and b"\r\n" in z.read(n)]
ck("第5条 批次包非 .sh 文件统一 0644", others == {0o644}, f"权限集合={[oct(o) for o in others]}")
ck("第5条 批次包保持 LF（无 CRLF）", not crlf, f"CRLF 文件数={len(crlf)}")
ck("第5条 批次包无重复前缀条目",
   not any(n.startswith(f"{BATCH_DIR.name}/FIN3-WKN-150/FIN3-WKN-150") for n in names))
ck("第5条 批次包第二层唯一题目目录",
   all(n.split("/")[1] == "FIN3-WKN-150" for n in names if n.count("/") >= 1 and n.split("/")[1]))

# ---------- 第 6 条：判据版本说明统一 ----------
doc = (TD / "交付文档.md").read_text(encoding="utf-8")
ck("第6条 交付文档新增 §9.1 判据版本变更史", "### 9.1 判据版本变更史" in doc)
ck("第6条 §9 汇总表登记「有（限定 2 条）」改动判据", "有（限定 2 条）" in doc)
ck("第6条 存在矛盾的旧表述已清除",
   "判据（36 条 / 权重 / `S_max = 220`）与上一轮**完全一致、未作任何修改**" not in doc)
ck("第6条 交付文档新增 §10 第四轮记录", "## 10. 第四轮整改记录" in doc)

# ---------- 第 1 条：判据 36 条 / 权重 / S_max 未变 ----------
toml = tomllib.loads((TD / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
items = toml.get("criterion") or toml.get("items") or toml.get("rubrics") or []
js = json.loads((TD / "rubrics.json").read_text(encoding="utf-8"))
jitems = js.get("items") or []
ck("第1条 运行态 rubrics.toml 判据条数 = 36", len(items) == 36, f"实际={len(items)}")
ck("第1条 设计态 rubrics.json 判据条数 = 36", len(jitems) == 36, f"实际={len(jitems)}")

tdesc = {i.get("id"): (i.get("description") or "") for i in items}
jdesc = {i.get("id"): (i.get("description") or "") for i in jitems}
diff = [k for k in tdesc if tdesc[k] != jdesc.get(k)]
ck("第1条 双文件 36 条 description 逐字一致", not diff, f"不一致={diff}")
smax = (js.get("metadata") or {}).get("scoring", {}).get("s_max")
ck("第1条 S_max = 220", smax == 220, f"实际={smax}")
neg = sum(1 for i in jitems if i.get("negate"))
ck("第1条 负向判据 2 条 / 正向 34 条", neg == 2 and len(jitems) - neg == 34, f"negate={neg}")

# ---------- 第 3 条：PNG 留在 FIN3-WKN-150_charts 子目录，不得移位 ----------
for base, tag in ((TD / "solution" / "golden_output", "golden"),
                  (ARC / "oracle" / "output", "oracle")):
    pngs = sorted(p.name for p in (base / "FIN3-WKN-150_charts").glob("*.png")) \
        if (base / "FIN3-WKN-150_charts").is_dir() else []
    stray = sorted(p.name for p in base.glob("*.png"))
    ck(f"第3条 {tag} 五张 PNG 在 FIN3-WKN-150_charts/ 且根目录无散落",
       len(pngs) == 5 and not stray, f"子目录={len(pngs)} 根目录={stray}")

# ---------- 第 2/7 条 + 返修要求：分数、门禁、难度同步 ----------
res = {}
for ex in ("oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"):
    res[ex] = json.loads((ARC / ex / "reward.json").read_text(encoding="utf-8"))
    ck(f"返修 四场 {ex} criteria_counted=36 且 verifier_error=0",
       res[ex]["criteria_counted"] == 36 and res[ex]["verifier_error"] == 0,
       f"counted={res[ex]['criteria_counted']} err={res[ex]['verifier_error']}")

mean = sum(res[e]["reward"] for e in ("qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol")) / 3
ck("第2条 G4 oracle > 0.85", res["oracle"]["reward"] > 0.85, f"{res['oracle']['reward']}")
ck("第2条 G5 三模型均分 < 0.70", mean < 0.70, f"{mean:.6f}")
ck("第2条 三模型均有得分", all(res[e]["reward"] > 0 for e in
                          ("qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol")), "")

sc = json.loads((ARC / "summary.json").read_text(encoding="utf-8"))
ck("返修 summary.json 已同步本轮分数",
   abs(sc["mean"] - round(mean, 6)) < 1e-9 and sc["task_version"] == "1.0.6"
   and sc["gate_pass"] is True and sc["declared_difficulty"] == "A1",
   f"mean={sc['mean']} ver={sc['task_version']} gate={sc['gate_pass']} 难度={sc['declared_difficulty']}")
ck("返修 上一轮四场分数已入 invalid_runs 留痕",
   any("fix5" in (r.get("round") or "") for r in sc["invalid_runs"]),
   f"invalid_runs={len(sc['invalid_runs'])}")

t = tomllib.loads((TD / "task.toml").read_text(encoding="utf-8"))
ck("返修 task.toml version=1.0.6", t["task"]["version"] == "1.0.6", t["task"]["version"])
ck("返修 difficulty 仍为 A1", t["metadata"].get("difficulty") == "A1",
   str(t["metadata"].get("difficulty")))

# ---------- 收尾：无残留 ----------
ck("收尾 无 _rejudge / __pycache__ 残留",
   not list(BATCH_DIR.rglob("_rejudge")) and not list(BATCH_DIR.rglob("__pycache__")))
with zipfile.ZipFile(BATCH_ZIP) as z:
    ns = z.namelist()
ck("收尾 批次包无 _rejudge / 缓存",
   not any("_rejudge" in n or "__pycache__" in n or ".pytest_cache" in n for n in ns))

print(f"{'':2} {'检查项':<52} 说明")
print("-" * 116)
for flag, item, detail in rows:
    print(f"{flag:2} {item:<52} {detail}")
print("-" * 116)
print(f"共 {len(rows)} 项，未通过 {bad} 项 → {'全部闭环 ✅' if bad == 0 else '存在未闭环项 ❌'}")
sys.exit(1 if bad else 0)
