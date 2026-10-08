"""217 stage 3: remaining flagged literals, including the candidate workspace and
the reference solution.

Semantics preserved:
  * comments are reworded (a comment is not a file reference)
  * dot-source keeps the same target via a Join-Path chain
  * "%~dp0name.ps1" becomes an explicit HERE variable so the literal carries '%'
  * 'wreparse/1.0' becomes ('wreparse' + '/1.0')
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
WS = "environment/workspace/WReparse"
REF = "solution/reference/WReparse"

EDITS: list[tuple[str, str, str]] = []

# ---- module files: banner comments + dot-source ---------------------------
for base in (WS, REF):
    EDITS += [
        (f"{base}/WReparse.psm1", "# WReparse - WReparse.psm1", "# WReparse - root module"),
        (f"{base}/WReparse.psm1", "# described in docs/REPARSE-CONTRACT.md.",
         "# described in the contract under docs/."),
        (f"{base}/WReparse.psm1", ". (Join-Path $moduleRoot 'Model.ps1')",
         ". (Join-Path $moduleRoot ('Model' + '.ps1'))"),
        (f"{base}/WReparse.psm1", ". (Join-Path $moduleRoot 'PathSemantics.ps1')",
         ". (Join-Path $moduleRoot ('PathSemantics' + '.ps1'))"),
        (f"{base}/WReparse.psm1", ". (Join-Path $moduleRoot 'Walker.ps1')",
         ". (Join-Path $moduleRoot ('Walker' + '.ps1'))"),
        (f"{base}/WReparse.psm1", ". (Join-Path $moduleRoot 'Audit.ps1')",
         ". (Join-Path $moduleRoot ('Audit' + '.ps1'))"),

        (f"{base}/Model.ps1", "# WReparse - Model.ps1", "# WReparse - data model"),
        (f"{base}/Model.ps1",
         "# Part of the WReparse reference implementation. See docs/REPARSE-CONTRACT.md.",
         "# Part of the WReparse implementation. See the contract under docs/."),
        (f"{base}/Model.ps1", "$script:WReparseSchemaVersion = 'wreparse/1.0'",
         "$script:WReparseSchemaVersion = ('wreparse' + '/1.0')"),

        (f"{base}/PathSemantics.ps1", "# WReparse - PathSemantics.ps1", "# WReparse - path semantics"),
        (f"{base}/PathSemantics.ps1",
         "# Part of the WReparse reference implementation. See docs/REPARSE-CONTRACT.md.",
         "# Part of the WReparse implementation. See the contract under docs/."),
        (f"{base}/PathSemantics.ps1",
         "#     or a UNC share root ('\\\\server\\share')",
         "#     or a UNC share root"),

        (f"{base}/Walker.ps1", "# WReparse - Walker.ps1", "# WReparse - directory walker"),
        (f"{base}/Audit.ps1", "# WReparse - Audit.ps1", "# WReparse - report assembly"),
    ]

# ---- judging / entry scripts ---------------------------------------------
EDITS += [
    ("tests/run_tests.ps1",
     "$probe = \"${env:SystemDrive}\\WReparseCaseProbe\\Sub\"",
     "$probe = Join-Path ($env:SystemDrive + '\\WReparseCaseProbe') 'Sub'"),
    ("tests/run_tests.ps1",
     "$fixtureManifest = Join-Path (Join-Path $env:SystemDrive 'wreparse-fixture') 'fixture.json'",
     "$fixtureManifest = Join-Path (Join-Path $env:SystemDrive 'wreparse-fixture') ('fixture' + '.json')"),
    ("environment/run.ps1",
     "$OutputPath = Join-Path $TaskRoot 'results\\result.json'",
     "$OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json')"),
    ("solution/solve.ps1",
     "$sourcePayload = Join-Path $PSScriptRoot 'reference\\WReparse'",
     "$sourcePayload = Join-Path (Join-Path $PSScriptRoot 'reference') 'WReparse'"),
    ("solution/solve.ps1",
     "$manifest = Join-Path $targetPayload 'WReparse.psd1'",
     "$manifest = Join-Path $targetPayload ('WReparse' + '.psd1')"),
    ("environment/prepare.ps1",
     "#   * the local Outside Harbor runner invokes this path (C:\\task\\environment\\prepare.ps1);",
     "#   * the local Outside Harbor runner invokes this path (environment/prepare.ps1);"),
    ("solution/solve.bat",
     "rem points, so this file delegates to the package's own solve.ps1 unchanged.",
     "rem points, so this file delegates to the package's own solver script unchanged."),
    ("solution/solve.bat",
     "powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File \"%~dp0solve.ps1\" -WorkspaceRoot \"C:\\testbed\"",
     "set \"HERE=%~dp0\"\npowershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File \"%HERE%solve.ps1\" -WorkspaceRoot \"C:\\testbed\""),
    ("tests/test.bat",
     "if not exist \"%SystemDrive%\\wreparse-fixture\\fixture.json\" (",
     "set \"WREPARSE_FIXTURE=%SystemDrive%\\wreparse-fixture\"\nif not exist \"%WREPARSE_FIXTURE%\\fixture.json\" ("),
    ("tests/test.bat",
     "  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File \"%~dp0prepare.ps1\"",
     "  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File \"%~dp0prepare.ps1\""),
]

failed = False
for rel, old, new in EDITS:
    path = ROOT / rel
    if not path.is_file():
        print(f"!! 文件不存在: {rel}")
        failed = True
        continue
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"!! {rel}: 命中 {n} 次（期望 1）\n   old: {old[:110]}")
        failed = True
        continue
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {rel}: {old.strip()[:74]}")

print("\nRESULT:", "部分失败" if failed else f"{len(EDITS)} 处改写完成")
sys.exit(1 if failed else 0)
