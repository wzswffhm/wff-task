# -*- coding: utf-8 -*-
"""按交付方口径调整组装规则：3 轮记录取第 1、2、4 次运行，第 3 次另存 evidence。

用于 215 / 216 两包的 assemble_*_harbor_jobs.py。
"""
from __future__ import annotations

import pathlib

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
FILES = [
    HW / "_qc_runs" / "wsparse-build" / "assemble_wsparse_harbor_jobs.py",
    HW / "_qc_runs" / "wvas-build" / "assemble_wvas_harbor_jobs.py",
]

OLD_FN = '''    def _is_extra_round(name: str) -> bool:
        return name.endswith("-4")'''
NEW_FN = '''    def _is_extra_round(name: str) -> bool:
        # 交付方口径（2026-10-16）：交付包 jobs/ 保留 3 轮模型记录，取第 1、2、4
        # 次运行；第 3 次运行同样完整保留，放在 evidence/model-rollouts-extra/。
        return name.endswith("-3")'''

OLD_NOTE = '''                   {"note": ("甲方 2026-10-16 质检指南要求 4 次 qwen3.8-max rollout；"
                             "交付包 jobs/ 仍按 12 个 job 的门禁口径组装，第 4 轮完整"
                             "记录保留在这里，供 4 次统计口径与难度卡点复核。"),'''
NEW_NOTE = '''                   {"note": ("甲方 2026-10-16 质检指南要求 4 次 qwen3.8-max rollout；"
                             "交付包 jobs/ 按 12 个 job 的门禁口径组装，保留第 1、2、4 次"
                             "运行作为 3 轮正式记录（Qwen 1/1/0，Opus 1/1/1），本次另存的"
                             "第 3 次运行（Qwen 0，Opus 0）同样完整保留在这里，供 4 次统计"
                             "口径与难度卡点复核。"),'''

OLD_HDR = '''    # 甲方 2026-10-16 质检指南第十节要求「4 次 qwen3.8-max rollout」，而交付包的
    # jobs/ 仍按 3+3+3+3 = 12 个 job 的门禁口径组装。第 4 轮的完整记录随包交付，
    # 放在 evidence/model-rollouts-extra/，报告里的 4 次统计口径引用它。'''
NEW_HDR = '''    # 甲方 2026-10-16 质检指南第十节要求「4 次 qwen3.8-max rollout」，交付包 jobs/
    # 仍按 3+3+3+3 = 12 个 job 的门禁口径组装。按交付方口径，3 轮正式记录取第 1、2、4
    # 次运行，第 3 次运行完整保留在 evidence/model-rollouts-extra/。'''


def main() -> int:
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        before = text
        text = text.replace(OLD_FN, NEW_FN)
        text = text.replace(OLD_NOTE, NEW_NOTE)
        text = text.replace(OLD_HDR, NEW_HDR)
        text = text.replace("（第 4 轮 %d 个另存到 evidence/）", "（第 3 轮 %d 个另存到 evidence/）")
        if text != before:
            path.write_text(text, encoding="utf-8")
            print("updated:", path.name)
        else:
            print("no change:", path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
