# WReparse - visible smoke test
#
# Covers one thing only: the report this module produces can be read back by the
# module itself. It does NOT check any clause of the behaviour contract, and
# passing it does NOT mean the implementation matches docs/REPARSE-CONTRACT.md.
# The grader runs a separate contract-conformance suite.
#
# Exit codes: 0 pass; 1 fail.

[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Split-Path -Parent $PSScriptRoot
}

$modulePath = Join-Path (Join-Path $WorkspaceRoot 'WReparse') ('WReparse' + '.psd1')
if (-not (Test-Path -LiteralPath $modulePath)) {
    Write-Host "smoke: module not found at $modulePath"
    exit 1
}

Import-Module $modulePath -Force

$failed = 0

# 1) the module imports and can report its schema version
try {
    $version = Get-WReparseSchemaVersion
    if ([string]::IsNullOrWhiteSpace([string]$version)) { throw 'schema version is empty' }
    Write-Host "[PASS] module imports; SchemaVersion = $version"
}
catch {
    Write-Host "[FAIL] import or Get-WReparseSchemaVersion failed: $($_.Exception.Message)"
    $failed++
}

# 2) scanning a scratch directory yields a report carrying Records / Errors / Stats
$probe = Join-Path $env:TEMP ('wreparse-smoke-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path (Join-Path $probe 'sub') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $probe 'a.txt') -Value 'a' -NoNewline -Encoding ASCII
$report = $null
try {
    $report = Get-WReparseReport -Root $probe
    foreach ($field in @('Records', 'Errors', 'Stats')) {
        if ($null -eq $report.PSObject.Properties[$field]) { throw "report is missing $field" }
    }
    Write-Host '[PASS] report carries Records / Errors / Stats'
}
catch {
    Write-Host "[FAIL] Get-WReparseReport failed: $($_.Exception.Message)"
    $failed++
}

# 3) the report serialises to JSON
try {
    $json = ConvertTo-WReparseJson -Report $report
    if ([string]::IsNullOrWhiteSpace([string]$json)) { throw 'serialised report is empty' }
    Write-Host '[PASS] report serialises to JSON'
}
catch {
    Write-Host "[FAIL] ConvertTo-WReparseJson failed: $($_.Exception.Message)"
    $failed++
}

# 4) the path helper is callable
try {
    $canonical = Get-WReparseCanonicalPath -Path $probe
    if ([string]::IsNullOrWhiteSpace([string]$canonical)) { throw 'canonical path is empty' }
    Write-Host '[PASS] Get-WReparseCanonicalPath is callable'
}
catch {
    Write-Host "[FAIL] Get-WReparseCanonicalPath failed: $($_.Exception.Message)"
    $failed++
}

Remove-Item -LiteralPath $probe -Recurse -Force -ErrorAction SilentlyContinue

if ($failed -gt 0) {
    Write-Host "smoke: $failed check(s) failed"
    exit 1
}
Write-Host 'smoke: all checks passed (this does NOT mean the module matches docs/REPARSE-CONTRACT.md)'
exit 0
