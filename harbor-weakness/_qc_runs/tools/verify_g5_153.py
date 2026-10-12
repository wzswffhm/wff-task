# -*- coding: utf-8 -*-
"""FIN3-WKN-153 G5 判分复算与判据漂移校验（依据 delivery/06-model-validation.md §7.1/§7.2）。

Score = ( Σ_正分项 w_i·v_i − Σ_negate项 w_j·(1−v_j) ) / Σ_正分项 w_i
- negate 条目 value=1.0 表示"未触发违规"；likert 归一再按 (raw-1)/4。
- 同时逐条比对 reward-details 的 weight/description 与现行 tests/rubrics.toml（判据漂移检查）。

用法: python verify_g5_153.py
"""
import json
import pathlib
import sys
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = H / "work_fin-b01_20261012-153" / "FIN3-WKN-153"
TOML = TASK / "tests" / "rubrics.toml"

RUNS = {
    "oracle": H / "_qc_runs/g4-153/trials/oracle-153/verifier",
    "gpt-5.6-sol": H / "_qc_runs/g5-153-gpt/trials/gpt56sol-153/verifier",
    "qwen3.8-max-0902": H / "_qc_runs/g5-153-qwen/trials/qwen38max-153-reg1/verifier",
}


def load_spec():
    data = tomllib.loads(TOML.read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["criterion"]}


def norm(x):
    return " ".join((x or "").split())


def main():
    spec = load_spec()
    neg_ids = sorted(k for k, v in spec.items() if v.get("negate"))
    w_pos = sum(float(v.get("weight") or 0.0) for k, v in spec.items() if k not in neg_ids)
    print(f"[spec] criteria={len(spec)} negate={neg_ids} W_pos(正分池权重和)={w_pos}")
    for model, d in RUNS.items():
        rp, dp = d / "reward.json", d / "reward-details.json"
        if not rp.is_file() or not dp.is_file():
            print(f"[skip] {model}: 缺 reward.json / reward-details.json -> {d}")
            continue
        rew = json.loads(rp.read_text(encoding="utf-8"))
        det = json.loads(dp.read_text(encoding="utf-8"))["reward"]
        crits = det["criteria"]
        if model == "qwen3.8-max-0902":
            print(f"[keys] {sorted(crits[0].keys())}")
        pos = 0.0
        neg = 0.0
        drift = []
        for c in crits:
            cid = c.get("id") or c.get("name")
            t = spec.get(cid)
            w = float(c.get("weight") or 0.0)
            if c.get("value") is not None:
                v = float(c["value"])
            elif c.get("raw") is not None:
                v = (float(c["raw"]) - 1.0) / 4.0
            else:
                v = 0.0
            is_neg = cid in neg_ids
            if is_neg:
                neg += w * (1.0 - v)
            else:
                pos += w * v
            if t is None:
                drift.append((cid, "unknown-id"))
            else:
                tw = float(t.get("weight") or 0.0)
                if abs(tw - w) > 1e-9:
                    drift.append((cid, "weight", tw, w))
                if norm(t.get("description")) != norm(c.get("description")):
                    drift.append((cid, "description-differs"))
        calc = (pos - neg) / w_pos if w_pos else 0.0
        ok = abs(calc - float(rew.get("reward") or 0.0)) < 5e-6
        print(
            f"[{model}] reward.json={rew.get('reward')} details.score={det.get('score')} "
            f"recomputed={round(calc, 6)} match={'PASS' if ok else 'FAIL'} | "
            f"sum_w_v={pos} neg_penalty={round(neg, 6)} criteria={len(crits)} "
            f"verifier_error={rew.get('verifier_error')} drift={len(drift)}"
        )
        for m in drift[:8]:
            print("    drift:", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
