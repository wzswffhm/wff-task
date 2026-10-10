# -*- coding: utf-8 -*-
"""核查 qwen N01 判定是否误判（negate 语义）——读完整 reasoning + 对照金标与交付物实际内容。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\_qc_runs")
RD = Q / "g5-152v4-qwen" / "trials" / "qwen38max-152v4" / "verifier" / "graded" / "reward-details.json"
if not RD.exists():
    RD = Q / "g5-152v4-qwen" / "trials" / "qwen38max-152v4" / "verifier" / "reward-details.json"

j = json.loads(RD.read_text(encoding="utf-8"))
r = j.get("reward", j)
crit = {c["id"]: c for c in r.get("criteria", [])}

print("=" * 100)
print("N01 完整记录")
print("=" * 100)
c = crit.get("N01")
print(f"  value={c.get('value')}  weight={c.get('weight')}  negate=?  raw={c.get('raw')}")
print(f"  name={c.get('name')}")
print()
print("--- description（判据原文）---")
print(c.get("description", "")[:900])
print()
print("--- reasoning（判官完整评语）---")
print(c.get("reasoning", ""))

print()
print("=" * 100)
print("对照：N01 的 negate 标记与 rewardkit 语义")
print("=" * 100)
import tomllib
t = tomllib.loads(pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152\tests\rubrics.toml"
).read_text(encoding="utf-8"))
for cc in t["criterion"]:
    if cc["id"] in ("N01",):
        print(f"  toml: {cc['id']} negate={cc.get('negate')} weight={cc.get('weight')}")
print("  语义: negate 条目 value=1 → 未违规(不扣)；value=0 → 触发违规(扣 weight)")
print("  若评语说『均已修正』却 value=0 → 疑似判官误判（或评语后半段另有残留）")

print()
print("=" * 100)
print("其他 8 条失分判据的 reasoning 是否也存在『做对了却给 0』的矛盾")
print("=" * 100)
for cid in ("R04", "R06", "R13", "R17", "R27", "R31", "R32", "R36"):
    cc = crit.get(cid)
    if not cc:
        continue
    rs = str(cc.get("reasoning", ""))
    # 找"但是/However"之后的否定结论
    tail = rs[-400:] if len(rs) > 400 else rs
    print(f"  --- {cid} (value={cc.get('value')}) 评语尾部 ---")
    print(f"      {tail.replace(chr(10), ' ')[:380]}")
