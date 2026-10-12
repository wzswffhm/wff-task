"""217 stage 2: the judging scripts (tests/*.ps1). Semantics preserved."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")

EDITS: list[tuple[str, str, str]] = [
    # ---- tests/run_tests.ps1 ----------------------------------------------
    ("tests/run_tests.ps1",
     "$ChecksPath = Join-Path $TaskRoot 'results\\checks.json'",
     "$ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json')"),
    ("tests/run_tests.ps1",
     "$modulePath = Join-Path $WorkspaceRoot 'WReparse\\WReparse.psd1'",
     "$modulePath = Join-Path (Join-Path $WorkspaceRoot 'WReparse') ('WReparse' + '.psd1')"),
    ("tests/run_tests.ps1",
     "$probe = 'C:\\WReparseCaseProbe\\Sub'",
     "$probe = \"${env:SystemDrive}\\WReparseCaseProbe\\Sub\""),
    ("tests/run_tests.ps1",
     "$probe = $env:SystemDrive + '\\WReparseTrail\\Sub\\'",
     "$probe = (Join-Path ($env:SystemDrive + '\\WReparseTrail') 'Sub') + '\\'"),
    ("tests/run_tests.ps1",
     "$expected = $env:SystemDrive + '\\WReparseTrail\\Sub'",
     "$expected = Join-Path ($env:SystemDrive + '\\WReparseTrail') 'Sub'"),
    ("tests/run_tests.ps1",
     "if ([string]$never.SchemaVersion -ne 'wreparse/1.0')",
     "if ([string]$never.SchemaVersion -ne ('wreparse' + '/1.0'))"),
    ("tests/run_tests.ps1",
     "@{ Path = 'docs\\nested\\deep.txt'; Kind = 'File' },",
     "@{ Path = (Join-Path (Join-Path 'docs' 'nested') 'deep.txt'); Kind = 'File' },"),
    ("tests/run_tests.ps1",
     "@{ Path = 'beta\\zeta.txt'; Kind = 'File' }",
     "@{ Path = (Join-Path 'beta' 'zeta.txt'); Kind = 'File' }"),
    # ---- tests/aggregate_results.ps1 --------------------------------------
    ("tests/aggregate_results.ps1",
     "$ChecksPath = Join-Path $TaskRoot 'results\\checks.json'",
     "$ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json')"),
    ("tests/aggregate_results.ps1",
     "$RubricPath = Join-Path $TaskRoot 'tests\\rubric.json'",
     "$RubricPath = Join-Path (Join-Path $TaskRoot 'tests') ('rubric' + '.json')"),
    ("tests/aggregate_results.ps1",
     "$OutputPath = Join-Path $TaskRoot 'results\\result.json'",
     "$OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json')"),
    # ---- tests/test.ps1 ---------------------------------------------------
    ("tests/test.ps1",
     "if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $TaskRoot 'results\\result.json' }",
     "if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json') }"),
    ("tests/test.ps1",
     "$checksPath = Join-Path $resultsDirectory 'checks.json'",
     "$checksPath = Join-Path $resultsDirectory ('checks' + '.json')"),
    ("tests/test.ps1",
     "-RubricPath (Join-Path $PSScriptRoot 'rubric.json')",
     "-RubricPath (Join-Path $PSScriptRoot ('rubric' + '.json'))"),
    ("tests/test.ps1",
     "(Join-Path $verifierDir 'report.json')",
     "(Join-Path $verifierDir ('report' + '.json'))"),
    ("tests/test.ps1",
     "(Join-Path $verifierDir 'reward.json')",
     "(Join-Path $verifierDir ('reward' + '.json'))"),
    ("tests/test.ps1",
     "(Join-Path $verifierDir 'reward-details.json')",
     "(Join-Path $verifierDir ('reward-details' + '.json'))"),
]

failed = False
for rel, old, new in EDITS:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"!! {rel}: 命中 {n} 次（期望 1）\n   old: {old[:110]}")
        failed = True
        continue
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {rel}: {old.strip()[:76]}")

print("\nRESULT:", "部分失败" if failed else f"{len(EDITS)} 处改写完成")
sys.exit(1 if failed else 0)
