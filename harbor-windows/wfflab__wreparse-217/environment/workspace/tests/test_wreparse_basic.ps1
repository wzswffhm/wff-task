# WReparse - visible smoke test
#
# 覆盖面刻意收窄到「能不能跑起来」：模块能导入、能产出报告对象、报告能序列化。
# 它不检查 docs/REPARSE-CONTRACT.md 的任何条款，也**刻意不检查报告的字段结构**、
# 排序或语义 —— 过了它不代表实现正确。判官会另跑完整的契约一致性套件。
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

# 1) the module imports and returns some schema version (value is not asserted)
try {
    $version = Get-WReparseSchemaVersion
    if ([string]::IsNullOrWhiteSpace([string]$version)) { throw 'schema version is empty' }
    Write-Host '[PASS] module imports and returns a schema version'
}
catch {
    Write-Host "[FAIL] import or Get-WReparseSchemaVersion failed: $($_.Exception.Message)"
    $failed++
}

# 2) a scan produces a report object -- field names are deliberately NOT checked,
#    so passing this says nothing about the report shape.
$probe = Join-Path $env:TEMP ('wreparse-smoke-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path (Join-Path $probe 'sub') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $probe 'a.txt') -Value 'a' -NoNewline -Encoding ASCII
$report = $null
try {
    $report = Get-WReparseReport -Root $probe
    if ($null -eq $report) { throw 'report is null' }
    Write-Host '[PASS] Get-WReparseReport returns a report object'
}
catch {
    Write-Host "[FAIL] Get-WReparseReport failed: $($_.Exception.Message)"
    $failed++
}

# 3) the report serialises to a non-empty string (structure is not asserted)
try {
    $json = ConvertTo-WReparseJson -Report $report
    if ([string]::IsNullOrWhiteSpace([string]$json)) { throw 'serialised report is empty' }
    Write-Host '[PASS] report serialises to a non-empty string'
}
catch {
    Write-Host "[FAIL] ConvertTo-WReparseJson failed: $($_.Exception.Message)"
    $failed++
}

# 4) the path helper is callable (return value is not asserted)
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
