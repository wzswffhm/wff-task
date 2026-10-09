# -*- coding: utf-8 -*-
"""方案 A：把 R29/R30 判据回退到「收紧前（= 判分快照）」版本，使包内自洽。

来源（已验证逐条等于四场判分快照）：
  work_fin-b01_20261006_fix3-150/FIN3-WKN-150/tests/rubrics.toml   sha 66e50b0c…
  work_fin-b01_20261006_fix3-150/FIN3-WKN-150/rubrics.json         sha aa09d645…

目标（4 处，字节级覆盖）：
  题包本体 FIN3-WKN-150/{tests/rubrics.toml, rubrics.json}
  批次副本 work-金融-私募股权投资-20261008/FIN3-WKN-150/{tests/rubrics.toml, rubrics.json}
"""
import hashlib
import json
import pathlib
import shutil
import sys
import datetime
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
CAND = H / "work_fin-b01_20261006_fix3-150" / "FIN3-WKN-150"
BODY = H / "FIN3-WKN-150"
BATCH = H / "work-金融-私募股权投资-20261008" / "FIN3-WKN-150"
QB = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")

SRC_TOML = CAND / "tests" / "rubrics.toml"
SRC_JSON = CAND / "rubrics.json"
DST = [
    (SRC_TOML, BODY / "tests" / "rubrics.toml"),
    (SRC_JSON, BODY / "rubrics.json"),
    (SRC_TOML, BATCH / "tests" / "rubrics.toml"),
    (SRC_JSON, BATCH / "rubrics.json"),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


print("=" * 100)
print("步骤 1/3：备份当前「收紧版」判据（留痕）")
print("=" * 100)
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
BK = QB / f"rubrics-tightened-backup-{ts}"
for p in [BODY / "tests" / "rubrics.toml", BODY / "rubrics.json"]:
    d = BK / p.relative_to(BODY)
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, d)
    print(f"  备份 {p.relative_to(H)}  sha={sha(p)[:16]}  {p.stat().st_size:,} B")
print(f"  -> {BK}")

print()
print("=" * 100)
print("步骤 2/3：字节级回退 4 处判据")
print("=" * 100)
for src, dst in DST:
    before = sha(dst)[:16] if dst.is_file() else "(无)"
    shutil.copyfile(src, dst)
    print(f"  {before} -> {sha(dst)[:16]}  {dst.relative_to(H)}")

print()
print("=" * 100)
print("步骤 3/3：验证")
print("=" * 100)
b_t, b_j = BODY / "tests" / "rubrics.toml", BODY / "rubrics.json"
c_t, c_j = BATCH / "tests" / "rubrics.toml", BATCH / "rubrics.json"
ok = True


def chk(label, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(f"  [{'OK' if cond else '!!'}] {label}{('  ' + extra) if extra else ''}")


chk("本体 toml == 批次 toml", sha(b_t) == sha(c_t), sha(b_t)[:16])
chk("本体 json == 批次 json", sha(b_j) == sha(c_j), sha(b_j)[:16])
chk("本体 toml == 候选(判分快照)版", sha(b_t) == sha(SRC_TOML), sha(b_t)[:16])
chk("本体 json == 候选版", sha(b_j) == sha(SRC_JSON), sha(b_j)[:16])

# 与四场判分快照逐条比对
ARCH = BATCH / "跑分产物与轨迹"
EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
toml_map = {c["id"]: c["description"] for c in
            tomllib.loads(b_t.read_text(encoding="utf-8"))["criterion"]}
json_map = {i["id"]: i for i in json.loads(b_j.read_text(encoding="utf-8"))["items"]}
chk("toml 36 条", len(toml_map) == 36, str(len(toml_map)))
chk("json 36 条", len(json_map) == 36, str(len(json_map)))
diff_jt = [k for k in toml_map if toml_map[k] != json_map.get(k, {}).get("description")]
chk("toml description == json description", not diff_jt, str(diff_jt))
for ex in EXEC:
    d = json.loads((ARCH / ex / "reward-details.json").read_text(encoding="utf-8"))["reward"]
    snap = {c["id"]: c["description"] for c in d["criteria"]}
    bad = [k for k in snap if snap[k] != toml_map.get(k)]
    chk(f"判分快照 == rubrics.toml  [{ex}]", not bad, str(bad) if bad else "")
txt = b_t.read_text(encoding="utf-8")
chk("无『量化拆解』(质检 #6 无关项，收紧已撤销)", "量化拆解" not in txt)
chk("无『跨期变化的量化幅度』", "跨期变化的量化幅度" not in txt)
chk("全文无『个别』(质检 #6)", "个别" not in txt)

# 与当前 rubrics.json 的 S_max 校验
crits = tomllib.loads(b_t.read_text(encoding="utf-8"))["criterion"]
smax = sum(c["weight"] for c in crits if not c.get("negate"))
chk("S_max == 220", smax == 220.0, str(smax))

print()
print(f">>> {'回退完成，包内已自洽（判据 == 判分），可过质检 #2/#6' if ok else '回退后仍有问题'}")
sys.exit(0 if ok else 1)
