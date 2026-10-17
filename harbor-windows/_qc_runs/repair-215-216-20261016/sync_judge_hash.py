# -*- coding: utf-8 -*-
"""同步 judge.toml 的 source_sha256 与 rubric.json（甲方 QC 会校验这个摘要）。

起因：216 把 f2p-file-backed-regions-are-a-subset 由 P2P 改判 F2P 时改了
rubric.json，但没有同步 judge.toml 里记录的摘要，QC preflight 直接报
"judge.toml rubric hash does not match rubric.json"。
"""
from __future__ import annotations

import hashlib
import pathlib
import re

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
PKGS = ["wfflab__wsparse-215-v1.0.1-delivery", "wfflab__wvas-216-v1.0.1-delivery"]


def main() -> int:
    for pkg in PKGS:
        root = HW / pkg
        rubric = root / "tests" / "rubric.json"
        judge = root / "tests" / "judge.toml"
        digest = hashlib.sha256(rubric.read_bytes()).hexdigest()
        text = judge.read_text(encoding="utf-8")
        old = re.search(r'source_sha256 = "([0-9a-f]{64})"', text)
        print(f"{pkg}: rubric.json sha256={digest}")
        if not old:
            print("  !! judge.toml 没有 source_sha256")
            continue
        if old.group(1) == digest:
            print("  judge.toml 已一致，无需修改")
        else:
            text = text.replace(old.group(1), digest)
            judge.write_text(text, encoding="utf-8")
            print(f"  judge.toml 已更新 {old.group(1)[:12]}... -> {digest[:12]}...")

        # 注释里的分组计数也要与 rubric 对齐
        data = rubric.read_text(encoding="utf-8")
        f2p = len(re.findall(r'"f2p-', data))
        p2p = len(re.findall(r'"p2p-', data))
        text = judge.read_text(encoding="utf-8")
        fixed = re.sub(r"\(F2P \d+ / P2P \d+\)", f"(F2P {f2p} / P2P {p2p})", text)
        fixed = re.sub(r"F2P \d+ / P2P \d+", f"F2P {f2p} / P2P {p2p}", fixed)
        if fixed != text:
            judge.write_text(fixed, encoding="utf-8")
            print(f"  judge.toml 注释已更新为 F2P {f2p} / P2P {p2p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
