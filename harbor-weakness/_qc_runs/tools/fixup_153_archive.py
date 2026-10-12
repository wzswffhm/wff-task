# -*- coding: utf-8 -*-
"""FIN3-WKN-153 跑分归档的「人工留档」补齐（幂等，归档后必跑）。

背景：`archive_153.py` 的 `archive_run()` 对每个执行体采取 `rmtree` 后重建，
会把人工补充的 `说明.md`、真实 agent 轨迹（`轨迹/claude-code.txt`、`轨迹/trajectory.json`）
以及 `trial.log` → `regrade-trial.log` 的改名一并清掉（2026-10-12 opus 归档时实测到）。
因此归档流程固定为两步：`archive_153.py` → 本脚本。

处理内容：
  - qwen3.8-max-0902：从完整 trial `qwen38max-153/agent` 补真实轨迹 + `说明.md`
  - claude-opus-4-8  ：从完整 trial `opus48-153/agent` 补真实轨迹 + `说明.md`
  - 两者：把 verifier-only 判分 trial 的 `轨迹/trial.log` 改名为 `regrade-trial.log`
（oracle / gpt 的归档由 archive_153.py 自行正确生成，无需处理。）

说明文本模板：`tools/notes_153/<模型目录名>.md`

用法: python fixup_153_archive.py [--check]
"""
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
DST = H / "work_fin-b01_20261012-153" / "跑分产物与轨迹"
Q = H / "_qc_runs"
NOTES = pathlib.Path(__file__).parent / "notes_153"

# 归档目录名 -> (完整 agent trial 的 agent 目录, 说明模板)
RUNS = {
    "qwen3.8-max-0902": Q / "g5-153-qwen" / "trials" / "qwen38max-153" / "agent",
    "claude-opus-4-8": Q / "g5-153-opus" / "trials" / "opus48-153" / "agent",
}
TRAJ = ["claude-code.txt", "trajectory.json"]


def main():
    check = "--check" in sys.argv
    problems = []
    for run, agent_dir in RUNS.items():
        out = DST / run
        if not out.is_dir():
            problems.append(f"{run}: 归档目录不存在 {out}")
            continue
        traj_dir = out / "轨迹"
        traj_dir.mkdir(parents=True, exist_ok=True)

        # 1) 真实 agent 轨迹
        for name in TRAJ:
            src = agent_dir / name
            if not src.is_file():
                problems.append(f"{run}: 源轨迹缺失 {src}")
                continue
            dst = traj_dir / name
            if check:
                if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
                    problems.append(f"{run}: 轨迹待补 {name}")
            else:
                shutil.copy2(src, dst)

        # 2) verifier-only 判分 trial 日志改名，避免与 agent trial 混淆
        old = traj_dir / "trial.log"
        new = traj_dir / "regrade-trial.log"
        if old.is_file():
            if check:
                problems.append(f"{run}: trial.log 待改名为 regrade-trial.log")
            else:
                if new.exists():
                    new.unlink()
                old.rename(new)

        # 3) 说明.md
        tpl = NOTES / f"{run}.md"
        if not tpl.is_file():
            problems.append(f"{run}: 说明模板缺失 {tpl}")
        elif check:
            dst = out / "说明.md"
            if not dst.is_file() or dst.read_bytes() != tpl.read_bytes():
                problems.append(f"{run}: 说明.md 待同步")
        else:
            shutil.copy2(tpl, out / "说明.md")

        if not check:
            files = sorted(p.name for p in traj_dir.iterdir())
            print(f"[{run}] 轨迹/ = {files}；说明.md 已同步")

    if check:
        if problems:
            print("[CHECK] 需修复：")
            for p in problems:
                print("   -", p)
            return 1
        print("[CHECK] 人工留档齐备，无需修复")
        return 0

    if problems:
        print("[WARN] 存在异常：")
        for p in problems:
            print("   -", p)
        return 1
    print("[OK] 人工留档已补齐")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
