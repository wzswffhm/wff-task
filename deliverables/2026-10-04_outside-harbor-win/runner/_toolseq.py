#!/usr/bin/env python3
"""Summarize tool-call sequence for a run's agent.log."""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs" / "wfflab__wreparse-217"

targets = sys.argv[1:] or [
    "20261005T132138-candidate-qwen3.8-max-0902-01",
    "20261005T132138-candidate-opus-5-01",
]

pat = re.compile(r"^--- turn (\d+) tool (\w+)")

for t in targets:
    d = RUNS / t
    for label in sorted(p for p in d.iterdir() if p.is_dir()) if d.is_dir() else []:
        log = label / "agent.log"
        if not log.exists():
            continue
        seq = []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = pat.match(line)
            if m:
                seq.append((int(m.group(1)), m.group(2)))
        c = Counter(n for _, n in seq)
        print("=" * 90)
        print(f"{t} [{label.name}]  tool_calls={len(seq)}  counts={dict(c)}")
        # collapse into readable run-length
        out = []
        for turn, name in seq:
            if out and out[-1][1] == name:
                out[-1][2] += 1
            else:
                out.append([turn, name, 1])
        print("  seq:", " ".join(f"{n}x{c}@{t}" for t, n, c in out))
