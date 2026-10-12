"""对比本包 jobs/ 与甲方参考包 harbor-record-42 的目录形状（文件相对路径集合）。

用法：python -X utf8 _qc_runs/tools/compare_archive_shapes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
REF = WS / "_qc_runs" / "ref42" / "winargv-windows-commandline-quoting" / "jobs"
OURS = WS / "deliverables" / "2026-10-11_wchunk216-jobs-archive" / "wfflab__wchunk-216" / "jobs"


def shape(jobs: Path) -> tuple[set[str], dict[str, set[str]], str | None]:
    root_files = {p.name for p in jobs.iterdir() if p.is_file()}
    per_trial: dict[str, set[str]] = {}
    for d in jobs.iterdir():
        if d.is_dir():
            per_trial[d.name] = {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()}
    ctrl, model = None, None
    for name, files in per_trial.items():
        tag = "control" if name.startswith("task0__") or "__o" in name else "model"
        if tag == "control" and ctrl is None:
            ctrl = name
        if tag == "model" and model is None:
            model = name
    return root_files, per_trial, (ctrl, model)


def main() -> int:
    ref_root, ref_trials, ref_rep = shape(REF)
    our_root, our_trials, our_rep = shape(OURS)

    print("== jobs/ 根文件 ==")
    print("  参考包:", sorted(ref_root))
    print("  本包  :", sorted(our_root))
    print("  缺失  :", sorted(ref_root - our_root) or "无")
    print("  新增  :", sorted(our_root - ref_root) or "无")

    # 参考包内控制轮/模型轮代表
    ref_ctrl = sorted(n for n in ref_trials if n.startswith("task0__"))
    ref_model = sorted(n for n in ref_trials if n.startswith("task__"))
    ref_ctrl_oracle = [n for n in ref_ctrl
                       if json.loads((REF / n / "result.json").read_text(encoding="utf-8-sig"))
                       ["verifier_result"]["rewards"]["reward"] == 1]
    ref_ctrl_nop = [n for n in ref_ctrl if n not in ref_ctrl_oracle]

    def role_of(jobs: Path, name: str) -> str:
        d = json.loads((jobs / name / "result.json").read_text(encoding="utf-8-sig"))
        if (d.get("agent_info") or {}).get("name") == "runner:LocalModelRunner":
            return "model"
        reward = d["verifier_result"]["rewards"]["reward"]
        return "control-oracle" if reward == 1 else "control-nop"

    our_roles: dict[str, list[str]] = {"control-oracle": [], "control-nop": [], "model": []}
    for n in sorted(our_trials):
        our_roles[role_of(OURS, n)].append(n)
    our_model = our_roles["model"]
    our_ctrl_oracle = our_roles["control-oracle"]
    our_ctrl_nop = our_roles["control-nop"]
    our_ctrl = our_ctrl_oracle + our_ctrl_nop

    def cmp(name: str, a: str, b: str) -> None:
        A, B = ref_trials[a], our_trials[b]
        print(f"\n== {name}：参考 {a} vs 本包 {b} ==")
        print(f"  仅参考有: {sorted(A - B) or '无'}")
        print(f"  仅本包有: {sorted(B - A) or '无'}")

    if ref_model and our_model:
        cmp("模型轮", ref_model[0], our_model[0])
    if ref_ctrl_oracle and our_ctrl_oracle:
        cmp("控制轮 · oracle", ref_ctrl_oracle[0], our_ctrl_oracle[0])
    if ref_ctrl_nop and our_ctrl_nop:
        cmp("控制轮 · nop", ref_ctrl_nop[0], our_ctrl_nop[0])

    print("\n== 计数 ==")
    print(f"  参考 trial 数 {len(ref_trials)}（model {len(ref_model)} / control {len(ref_ctrl)}）")
    print(f"  本包 trial 数 {len(our_trials)}（model {len(our_model)} / control {len(our_ctrl)}）")

    ref_cfg = json.loads((REF / "config.json").read_text(encoding="utf-8"))
    our_cfg = json.loads((OURS / "config.json").read_text(encoding="utf-8"))
    print("\n== config.json 顶层字段 ==")
    print("  参考:", list(ref_cfg))
    print("  本包:", list(our_cfg))
    ref_res = json.loads((REF / "result.json").read_text(encoding="utf-8"))
    our_res = json.loads((OURS / "result.json").read_text(encoding="utf-8"))
    print("== result.json 顶层字段 ==")
    print("  参考:", list(ref_res))
    print("  本包:", list(our_res))
    print("== result.json trials[] 字段 ==")
    print("  参考:", list(ref_res["trials"][0]))
    print("  本包:", list(our_res["trials"][0]))
    ref_lock = json.loads((REF / "lock.json").read_text(encoding="utf-8"))
    our_lock = json.loads((OURS / "lock.json").read_text(encoding="utf-8"))
    print("== lock.json 顶层字段 ==")
    print("  参考:", list(ref_lock))
    print("  本包:", list(our_lock))
    return 0


if __name__ == "__main__":
    sys.exit(main())
