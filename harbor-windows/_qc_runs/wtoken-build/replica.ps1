# Replica of tests/run_tests.ps1 staging, then run only the smoke-suite check
# with a long traceback so the child failure becomes visible.

$ErrorActionPreference = 'Continue'

$rr = Join-Path $env:TEMP ('replica-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $rr -Force | Out-Null
Write-Host "runRoot = $rr"

robocopy 'C:\testbed' $rr /E /XD .git __pycache__ .pytest_cache reports /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
Write-Host "robocopy exit = $LASTEXITCODE"

$testsDir = Join-Path $rr 'tests'
if (-not (Test-Path -LiteralPath $testsDir)) { New-Item -ItemType Directory -Path $testsDir -Force | Out-Null }
Copy-Item -LiteralPath 'C:\tests\test_wtoken_semantics.py' -Destination (Join-Path $testsDir 'test_wtoken_semantics.py') -Force

$conftest = @'
import pathlib
import sys

_root = str(pathlib.Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
'@
Set-Content -LiteralPath (Join-Path $rr 'conftest.py') -Value $conftest -Encoding UTF8

Write-Host '--- staged tests dir ---'
Get-ChildItem -LiteralPath $testsDir | ForEach-Object { '  ' + $_.Name }

$env:PYTHONPATH = "$rr;$env:PYTHONPATH"
Push-Location $rr
try {
    & 'C:\Python312\python.exe' -m pytest -rA --tb=long -p no:cacheprovider 'tests/test_wtoken_semantics.py::test_visible_smoke_suite_still_passes' 2>&1 | Out-Host
    Write-Host "pytest exit = $LASTEXITCODE"
}
finally {
    Pop-Location
}
