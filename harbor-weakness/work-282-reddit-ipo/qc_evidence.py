#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判分证据核验（evidence-checks §1.2/§1.3）：
1) 按 rewardkit 公式复算，必须与 reward.json 完全一致
2) reward-details 的 description/weight 与现行 tests/rubrics.toml 逐条零漂移
3) 记录未满分条目（供口径歧义排查 / 集中度检查）
4) 难度门槛判定
用法: python qc_evidence.py <verifier目录> [三模型跑分目录...]
"""
from __future__ import annotations

import json
import pathlib
import sys
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path("harbor-weakness/FIN3-WKN-152")
TOML = TASK / "tests/rubrics.toml"


def load_toml():
    d = tomllib.loads(TOML.read_bytes().decode("utf-8"))
    return d["criterion"]


def recalc(details) -> tuple[float, int, int]:
    """rewardkit: (Σ正 w·v − Σneg w·(1−v)) / Σ正w；异常条目不计。"""
    pos_w = neg_w = num = 0.0
    counted = abnormal = 0
    for c in details:
        w = float(c.get("weight", 0))
        v = c.get("value")
        if v is None:
            abnormal += 1
            continue
        v = float(v)
        if not (0.0 <= v <= 1.0):
            abnormal += 1
            continue
        if c.get("negate"):
            neg_w += w
            num -= w * (1.0 - v)
        else:
            pos_w += w
            num += w * v
        counted += 1
    if pos_w <= 0:
        return 0.0, counted, abnormal
    return max(0.0, min(1.0, num / pos_w)), counted, abnormal


def extract_criteria(d) -> list:
    """兼容 reward-details 的两种结构。"""
    r = d.get("reward") or d
    crit = r.get("criteria")
    if isinstance(crit, dict):
        out = []
        for k, v in crit.items():
            if isinstance(v, dict):
                v = {**v, "id": v.get("id", k)}
                out.append(v)
        return out
    if isinstance(crit, list):
        return crit
    # 逐维度形态
    out = []
    for dim, val in (d.get("details") or {}).items():
        items = val if isinstance(val, list) else [val]
        for it in items:
            if isinstance(it, dict) and ("weight" in it or "value" in it):
                out.append(it)
    return out


def audit(label: str, vdir: pathlib.Path, spec: list) -> dict | None:
    rj = vdir / "reward.json"
    rd = vdir / "graded/reward-details.json"
    if not rj.exists():
        print(f"\n### {label}: reward.json 缺失 → 未跑/未完成")
        return None
    reward = json.loads(rj.read_text(encoding="utf-8"))
    print(f"\n### {label}")
    print(f"  reward.json = {json.dumps(reward, ensure_ascii=False)}")
    exitmsg = vdir / "reward_exit_message.json"
    if exitmsg.exists():
        print(f"  ⚠ reward_exit_message.json 存在: {exitmsg.read_text(encoding='utf-8')[:160]}")
    if not rd.exists():
        print("  reward-details.json 缺失 → 评分未完成（fail-closed 占位），不计为有效证据")
        return None

    d = json.loads(rd.read_text(encoding="utf-8"))
    crit = extract_criteria(d)
    print(f"  reward-details 判据条数 = {len(crit)}")

    got, counted, abnormal = recalc(crit)
    declared = float(reward.get("reward", 0.0))
    ok = abs(got - declared) < 1e-6
    print(f"  复算 = {got:.6f}   reward.json = {declared:.6f}   {'一致 ✓' if ok else '不一致 ✗'}")
    print(f"  criteria_counted = {counted}（异常/缺值 {abnormal}）")

    # 零漂移：reward-details 与 toml 的 weight 均记录为**正数**，negate 单独标记
    spec_by_id = {c["id"]: c for c in spec}
    drift = []
    for c in crit:
        cid = c.get("id") or c.get("name")
        s = spec_by_id.get(cid)
        if s is None:
            drift.append(f"{cid}: toml 中不存在")
            continue
        if str(c.get("description", "")) != s["description"]:
            drift.append(f"{cid}: description 漂移")
        cw = float(c.get("weight", 0))
        sw = float(s["weight"])          # 不做符号转换
        if abs(cw - sw) > 1e-9:
            drift.append(f"{cid}: weight 漂移 (details={cw}, toml={sw})")
        cneg = bool(c.get("negate"))
        sneg = bool(s.get("negate"))
        if cneg != sneg:
            drift.append(f"{cid}: negate 漂移 (details={cneg}, toml={sneg})")
    print(f"  与现行 rubrics.toml 零漂移: {'✓' if not drift else '✗ ' + str(drift[:5])}")

    # 未满分条目
    notfull = [(c.get("id"), float(c.get("weight", 0)), float(c.get("value", 0)))
               for c in crit if float(c.get("value", 1)) < 1.0]
    zero = [x for x in notfull if x[2] == 0.0]
    print(f"  未满分 {len(notfull)} 条（其中 0 分 {len(zero)} 条）")
    if notfull:
        print("    " + ", ".join(f"{i}({w:g}×{v:g})" for i, w, v in notfull))

    return dict(label=label, reward=declared, recalc=got, ok=ok, counted=counted,
                drift=drift, notfull=notfull, zero=zero,
                verifier_error=float(reward.get("verifier_error", 0)))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    spec = load_toml()
    pos = [c for c in spec if not c.get("negate")]
    smax = sum(float(c["weight"]) for c in pos)
    print("=" * 92)
    print(f"现行判据: {len(spec)} 条（正 {len(pos)} / 负 {len(spec)-len(pos)}）  S_max = {smax}")
    print("=" * 92)

    res = []
    v = pathlib.Path(sys.argv[1])
    r = audit("oracle（G4 golden 预检）", v, spec)
    if r:
        res.append(r)

    print("\n" + "=" * 92)
    print("难度门槛判定（evidence-checks §1.3）")
    print("=" * 92)
    if r:
        o = r["reward"]
        print(f"  oracle = {o:.6f}   门槛 > 0.85   {'PASS ✓' if o > 0.85 else 'FAIL ✗'}")
        print(f"  verifier_error = {r['verifier_error']:g}   门槛 = 0   "
              f"{'PASS ✓' if r['verifier_error'] == 0 else 'FAIL ✗'}")
        print(f"  criteria_counted = {r['counted']}   期望 = {len(spec)}   "
              f"{'PASS ✓' if r['counted'] == len(spec) else '偏少，需核查'}")
        if r["drift"]:
            print("  description/weight 零漂移: FAIL ✗（该轮判分不能作为难度证据）")
        else:
            print("  description/weight 零漂移: PASS ✓")
    else:
        print("  无有效 oracle 判分 → 未验证（TBD）")

    # 三模型（若有）
    models = ["gpt-5.6-sol", "claude-opus-4-8", "qwen3.8-max-0902"]
    runs = []
    for m in models:
        for base in sys.argv[2:]:
            p = pathlib.Path(base) / m
            if p.is_dir():
                rr = audit(m, p, spec)
                if rr:
                    runs.append(rr)
                break
    if len(runs) == 3:
        mean = sum(x["reward"] for x in runs) / 3
        band = "A1" if 0.6 <= mean < 0.7 else ("A2" if 0.5 <= mean < 0.6 else
                ("A3" if mean < 0.5 else ">0.7 越档"))
        print("\n" + "=" * 92)
        print(f"三模型均分 = {mean:.6f}   门槛 < 0.70   {'PASS ✓' if mean < 0.7 else 'FAIL ✗'}")
        print(f"实测档位 = {band}   余量 = {(0.7-mean)*100:.1f}pp")
        print(f"至少一个模型非零 = {any(x['reward'] > 0 for x in runs)}")
        if (0.7 - mean) * 100 < 5:
            print("  ⚠ 余量 < 5pp：重跑判官存在越档风险（pitfall 案例 9）")
    else:
        print(f"\n三模型齐备度 = {len(runs)}/3 → G5 未完成（TBD）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
