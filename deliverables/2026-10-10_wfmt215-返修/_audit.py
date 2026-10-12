"""Audit: prove the agent-visible tree carries no answer and no hidden suite.

Reports (1) the full agent-visible inventory, (2) any hit for answer-shaped
material inside it, and (3) what the jobs/ evidence tree exposes.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-10_wfmt215-返修")
BUILD = ROOT / "build"
TASK = BUILD / "outside_harbor-assets" / "wfflab__wfmt-215"
JOBS = BUILD / "jobs"

# Answer-shaped material: the format constants the candidate must derive, the
# published CRC check value, and any pointer to the sealed material.
PATTERNS = [
    (r"CBF43926", "published CRC check value"),
    (r"E8B7BE43", "published CRC check value"),
    (r"ISO-HDLC", "CRC variant name"),
    (r"EDB88320", "CRC polynomial (reversed)"),
    (r"zlib\.crc32", "library shortcut"),
    (r"final xor|XOR out|异或输出", "CRC final complement"),
    (r"ALIGN\s*=\s*4|align to 4|4 字节对齐|对齐到 4", "record alignment answer"),
    (r"little.endian|小端", "endianness answer"),
    (r"HEADER_SIZE\s*=\s*9", "header layout answer"),
    (r"oracle\.patch", "oracle patch reference"),
    (r"test_wfmt_semantics", "hidden suite name"),
    (r"reference/wfmt", "reference implementation pointer"),
    (r"rubric\.conditions", "rubric conditions pointer"),
]

print("=" * 78)
print("AGENT-VISIBLE INVENTORY")
print("=" * 78)
files = sorted(p for p in TASK.rglob("*") if p.is_file())
for path in files:
    print(f"{path.stat().st_size:>9}  {path.relative_to(TASK)}")
print(f"total: {len(files)} files, {sum(p.stat().st_size for p in files)/1024:.1f} KiB")

print()
print("=" * 78)
print("ANSWER-SHAPED HITS INSIDE THE AGENT-VISIBLE TREE")
print("=" * 78)
hits = 0
for path in files:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        continue
    for pattern, label in PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            line = text[:match.start()].count("\n") + 1
            snippet = text.splitlines()[line - 1].strip()[:110]
            print(f"{path.relative_to(TASK)}:{line}  [{label}]  {snippet}")
            hits += 1
print(f"hits: {hits}")

print()
print("=" * 78)
print("JOBS EVIDENCE TREE")
print("=" * 78)
job_files = sorted(p for p in JOBS.rglob("*") if p.is_file())
print(f"files: {len(job_files)}, {sum(p.stat().st_size for p in job_files)/1024:.1f} KiB")
job_hits = 0
for path in job_files:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        continue
    for pattern, label in PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            job_hits += 1
            if job_hits <= 25:
                line = text[:match.start()].count("\n") + 1
                print(f"{path.relative_to(JOBS)}:{line}  [{label}]")
print(f"job hits: {job_hits}")
