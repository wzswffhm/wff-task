# -*- coding: utf-8 -*-
"""FIN3-WKN-150 判分数据全面审计：确保无旧数据残留。只读。

检查项：
 1) 四执行体 reward.json 值 / criteria_counted / verifier_error
 2) reward-details.json 的 score、判据条数、R29/R30 判据快照是否为收紧后文本
 3) summary.json 与各 reward.json 的一致性（mean 三模型均分，不含 oracle）
 4) fail-closed 残留（reward_exit_message.json）
 5) _rejudge 残留
 6) 旧值残留扫描（批次目录内除历史对照外的位置）
 7) 批次 zip 内判分数据与本地逐值一致
 8) rubrics 判据数与 S_max 与判分依据一致
 9) 151 / 149 归档判分未被误动
"""
import hashlib
import json
import pathlib
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BATCH = H / "work-金融-私募股权投资-20261008"
T = BATCH / "FIN3-WKN-150"
SCORE = T / "跑分产物与轨迹"
ZIP = H / "work_fin-b01_20261006_fix5-150.zip"

EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
G5_EXEC = ["qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
EXPECT = {
    "oracle": 0.996591,
    "qwen3.8-max-0902": 0.7875,
    "claude-opus-4-8": 0.476136,
    "gpt-5.6-sol": 0.640909,
}
OLD_VALUES = {
    "0.986364": "fix2 oracle(满分1.0之前的试次)",
    "1.000000": "fix3 oracle",
    "0.731818": "首轮 rejudge qwen",
    "0.651136": "首轮 rejudge opus",
    "0.718182": "首轮 rejudge gpt",
    "0.621970": "fix4 G5 均值",
    "0.672727": "fix3 gpt",
    "0.411364": "fix3 opus",
    "0.781818": "fix3 qwen",
}
problems = []


def chk(title, ok, detail=""):
    print(f"  [{'OK' if ok else '!!'}] {title}")
    if detail:
        for line in str(detail).split("\n"):
            print(f"        {line}")
    if not ok:
        problems.append(title)
    return ok


print("=" * 100)
print("1) 四执行体 reward.json")
print("=" * 100)
local_rewards = {}
for ex in EXEC:
    p = SCORE / ex / "reward.json"
    if not p.is_file():
        chk(f"{ex}/reward.json 存在", False, "文件缺失")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    v = d["reward"]
    local_rewards[ex] = v
    ok = (abs(v - EXPECT[ex]) < 1e-9 and d["criteria_counted"] == 36.0 and d["verifier_error"] == 0.0
          and abs(d.get("graded_score", v) - v) < 1e-9)
    chk(f"{ex}: reward={v} counted={d['criteria_counted']} err={d['verifier_error']} 期望={EXPECT[ex]}", ok)

print()
print("=" * 100)
print("2) reward-details.json（score 一致 / 判据条数 / R29-R30 快照新旧）")
print("=" * 100)
for ex in EXEC:
    p = SCORE / ex / "reward-details.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    r = d["reward"]
    score = r.get("score")
    crits = r.get("criteria")
    n = len(crits) if isinstance(crits, list) else None
    judge = r.get("judge")
    blob = json.dumps(r, ensure_ascii=False)
    has_r29 = "量化拆解" in blob
    has_r30 = "跨期变化的量化幅度" in blob
    ok = (abs(score - EXPECT[ex]) < 1e-9 and n == 36)
    print(f"  {ex}: score={score} criteria={n} judge={judge}")
    print(f"      R29收紧快照={'有' if has_r29 else '无'}  R30收紧快照={'有' if has_r30 else '无'}")
    chk(f"{ex}: details.score 与 reward.json 一致且 36 条", ok)
    # 打印 R29/R30 条目的判据文本片段（确认是收紧后）
    if isinstance(crits, list):
        for c in crits:
            cid = c.get("id") or c.get("criterion_id") or c.get("name")
            if cid in ("R29", "R30"):
                desc = str(c.get("description") or c.get("desc") or "")[:110]
                print(f"      {cid}: {desc}")

print()
print("=" * 100)
print("3) summary.json 一致性")
print("=" * 100)
s = json.loads((SCORE / "summary.json").read_text(encoding="utf-8"))
print(f"  task_version={s.get('task_version')}  round={s.get('round')}")
print(f"  mean={s.get('mean')}  gate={s.get('mean_gate')}  pass={s.get('gate_pass')}  difficulty={s.get('declared_difficulty')}")
runmap = {}
for run in s.get("runs", []):
    m = run.get("model")
    rv = run.get("reward")
    if isinstance(rv, dict):
        rv = rv.get("reward")
    runmap[m] = rv
    exp = EXPECT.get(m)
    flag = "OK" if (exp is not None and abs(rv - exp) < 1e-9) else "!!"
    print(f"    [{flag}] {m}: {rv}   (期望 {exp})")
g5 = [runmap[m] for m in G5_EXEC]
calc = sum(g5) / len(g5)
ok_mean = abs(calc - s["mean"]) < 1e-9
chk(f"summary.runs 与 reward.json 全部一致", all(abs(runmap.get(m, -1) - EXPECT[m]) < 1e-9 for m in EXEC))
chk(f"mean 复算 = {calc:.6f} 与 recorded {s['mean']} 一致（仅三模型，不含 oracle）", ok_mean)
chk(f"gate_pass 与 mean<0.70 一致", s["gate_pass"] == (s["mean"] < 0.70))
chk(f"task_version 为 1.0.5", s.get("task_version") == "1.0.5")

print()
print("=" * 100)
print("4) fail-closed 残留（reward_exit_message.json）")
print("=" * 100)
stale = [p.relative_to(SCORE).as_posix() for p in SCORE.rglob("reward_exit_message.json")]
chk("无 reward_exit_message.json 残留", not stale, stale)

print()
print("=" * 100)
print("5) _rejudge 残留")
print("=" * 100)
rj = [p.relative_to(H).as_posix() for p in H.rglob("_rejudge")]
chk("无 _rejudge 目录残留", not rj, rj)

print()
print("=" * 100)
print("6) 旧值残留扫描（批次目录内，排除交付文档的历史对照段）")
print("=" * 100)
hits = {}
for p in T.rglob("*"):
    if not p.is_file() or "__pycache__" in p.parts:
        continue
    rel = p.relative_to(T).as_posix()
    if rel.startswith("跑分产物与轨迹/"):
        continue  # 单独处理
    try:
        txt = p.read_text(encoding="utf-8")
    except Exception:
        continue
    for ov in OLD_VALUES:
        if ov in txt:
            hits.setdefault(ov, []).append(rel)
for ov, where in hits.items():
    print(f"  {ov} ({OLD_VALUES[ov]}): {where}")
print(f"  非交付文档位置命中旧值: {len([o for o in hits if not all(w=='交付文档.md' for w in hits[o])])}")
# 交付文档里旧值只允许出现在历史对照/试次说明段
doc = (T / "交付文档.md").read_text(encoding="utf-8")
doc_old_lines = [(i + 1, l.strip()[:120]) for i, l in enumerate(doc.splitlines())
                 if any(ov in l for ov in OLD_VALUES)]
print(f"  交付文档.md 含旧值行数: {len(doc_old_lines)}（应仅历史对照/试次留痕）")
for ln, l in doc_old_lines:
    print(f"      L{ln}: {l}")

print()
print("=" * 100)
print("7) 批次 zip 内判分数据与本地逐值一致")
print("=" * 100)
with zipfile.ZipFile(ZIP) as zf:
    names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    print(f"  zip={ZIP.name} {ZIP.stat().st_size:,} B  entries={len(names)}")
    print(f"  顶层={tops}  第二层={second}")
    zip_rewards = {}
    for ex in EXEC:
        zn = f"{tops[0]}/FIN3-WKN-150/跑分产物与轨迹/{ex}/reward.json"
        if zn in names:
            d = json.loads(zf.read(zn).decode("utf-8"))
            zip_rewards[ex] = d["reward"]
    zs = json.loads(zf.read(f"{tops[0]}/FIN3-WKN-150/跑分产物与轨迹/summary.json").decode("utf-8"))
    zrub = zf.read(f"{tops[0]}/FIN3-WKN-150/tests/rubrics.toml").decode("utf-8")
    zexit = [n for n in names if n.endswith("reward_exit_message.json")]
    zrej = [n for n in names if "/_rejudge/" in n]
for ex in EXEC:
    zv = zip_rewards.get(ex)
    ok = zv is not None and abs(zv - EXPECT[ex]) < 1e-9
    print(f"    [{'OK' if ok else '!!'}] 包内 {ex}/reward.json = {zv}")
chk("包内四场分数 == 本地", all(ex in zip_rewards and abs(zip_rewards[ex] - EXPECT[ex]) < 1e-9 for ex in EXEC))
chk(f"包内 summary.mean == {zs.get('mean')} 且 == 本地", abs(zs.get("mean", -1) - s["mean"]) < 1e-9)
chk("包内 rubrics.toml 含 R29/R30 收紧文本", "量化拆解" in zrub and "跨期变化的量化幅度" in zrub)
chk("包内无 reward_exit_message.json", not zexit, zexit)
chk("包内无 _rejudge", not zrej, zrej)

print()
print("=" * 100)
print("8) rubrics 判据数与 S_max 与判分依据一致")
print("=" * 100)
import tomllib
rub = tomllib.loads((T / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
crits = rub.get("criterion", [])
smax = sum(c["weight"] for c in crits if not c.get("negate"))
print(f"  判据数={len(crits)}  S_max(正权重){smax}")
chk("36 条判据", len(crits) == 36)
chk("S_max == 220", smax == 220.0)
j = json.loads((T / "rubrics.json").read_text(encoding="utf-8"))
chk("rubrics.json items == 36", len(j["items"]) == 36)

print()
print("=" * 100)
print("9) 151 / 149 归档判分未被误动")
print("=" * 100)
B151 = H / "work_fin-b01_20261005-151"
if not B151.is_dir():
    cand = [p for p in H.iterdir() if p.is_dir() and "151" in p.name]
    B151 = cand[0] if cand else None
if B151:
    print(f"  151 批次目录: {B151.name}")
    sc = B151 / "FIN3-WKN-151" / "跑分产物与轨迹"
    if sc.is_dir():
        for ex, exp in [("oracle", 0.967914), ("qwen3.8-max-0902", 0.721925),
                        ("claude-opus-4-8", 0.656417), ("gpt-5.6-sol", 0.59893)]:
            p = sc / ex / "reward.json"
            if p.is_file():
                v = json.loads(p.read_text(encoding="utf-8"))["reward"]
                print(f"    [{'OK' if abs(v-exp)<1e-9 else '!!'}] {ex}: {v} (期望 {exp})")
            else:
                # 可能结构不同，递归找
                print(f"    ? {ex}: reward.json 不在 {p.relative_to(B151)}")
    else:
        print(f"    ? 未找到 {sc.relative_to(B151)}")

print()
print("=" * 100)
print("汇总")
print("=" * 100)
print(f"  问题项 {len(problems)}: {problems if problems else '无'}")
print(f"  >>> {'判分数据全部为新值，无旧数据残留' if not problems else '存在待处理项'}")
