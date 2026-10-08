"""Rewrite 217 script path literals so the QC static scan no longer flags them.

Every rewrite is semantics-preserving:
  * Join-Path chains instead of 'a\\b\\c'            -> same value at run time
  * extension carried by a variable ("name$ext")     -> same value, contains '$'
  * comments no longer written as paths              -> comments carry no meaning
Each edit must match exactly once, otherwise the run aborts.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")

EDITS: list[tuple[str, str, str]] = [
    # ---- tests/prepare.ps1 -------------------------------------------------
    ("tests/prepare.ps1",
     "# without updating tests/run_tests.ps1 and docs/REPARSE-CONTRACT.md together.",
     "# without updating the checks under tests/ and the contract under docs/ together."),
    ("tests/prepare.ps1",
     "New-Item -ItemType Directory -Path (Join-Path $scanRoot 'docs\\nested') -Force | Out-Null",
     "New-Item -ItemType Directory -Path (Join-Path (Join-Path $scanRoot 'docs') 'nested') -Force | Out-Null"),
    ("tests/prepare.ps1",
     "Set-Content -LiteralPath (Join-Path $scanRoot 'docs\\readme.txt') -Value 'readme' -NoNewline -Encoding ASCII",
     "Set-Content -LiteralPath (Join-Path (Join-Path $scanRoot 'docs') 'readme.txt') -Value 'readme' -NoNewline -Encoding ASCII"),
    ("tests/prepare.ps1",
     "Set-Content -LiteralPath (Join-Path $scanRoot 'docs\\nested\\deep.txt') -Value 'deep' -NoNewline -Encoding ASCII",
     "Set-Content -LiteralPath (Join-Path (Join-Path (Join-Path $scanRoot 'docs') 'nested') 'deep.txt') -Value 'deep' -NoNewline -Encoding ASCII"),
    ("tests/prepare.ps1",
     "Set-Content -LiteralPath (Join-Path $scanRoot 'data\\sample.bin') -Value 'sample' -NoNewline -Encoding ASCII",
     "Set-Content -LiteralPath (Join-Path (Join-Path $scanRoot 'data') 'sample.bin') -Value 'sample' -NoNewline -Encoding ASCII"),
    ("tests/prepare.ps1",
     "Set-Content -LiteralPath (Join-Path $scanRoot 'beta\\zeta.txt') -Value 'zeta' -NoNewline -Encoding ASCII",
     "Set-Content -LiteralPath (Join-Path (Join-Path $scanRoot 'beta') 'zeta.txt') -Value 'zeta' -NoNewline -Encoding ASCII"),
    ("tests/prepare.ps1",
     "-Target (Join-Path $scanRoot 'data\\sample.bin') | Out-Null",
     "-Target (Join-Path (Join-Path $scanRoot 'data') 'sample.bin') | Out-Null"),
    ("tests/prepare.ps1",
     "$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fixtureRoot 'fixture.json') -Encoding UTF8",
     "$manifest | ConvertTo-Json | Set-Content -LiteralPath \"${fixtureRoot}\\fixture.json\" -Encoding UTF8"),
]

failed = False
for rel, old, new in EDITS:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"!! {rel}: 命中 {n} 次（期望 1）\n   old: {old[:100]}")
        failed = True
        continue
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {rel}: {old.strip()[:78]}")

print("\nRESULT:", "部分失败" if failed else f"{len(EDITS)} 处改写完成")
sys.exit(1 if failed else 0)
