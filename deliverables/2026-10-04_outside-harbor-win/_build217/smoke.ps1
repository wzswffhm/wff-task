# Build the canonical WReparse fixture tree and run a smoke pass with the
# reference implementation. Development helper; not part of the task package.
[CmdletBinding()]
param(
    [string]$Base = '',
    [string]$ModuleRoot = ''
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($Base)) { $Base = Join-Path $env:TEMP 'wreparse-fixture' }
if ([string]::IsNullOrWhiteSpace($ModuleRoot)) { $ModuleRoot = Join-Path $here 'oracle' }

if (Test-Path -LiteralPath $Base) { Remove-Item -LiteralPath $Base -Recurse -Force }
$scan = Join-Path $Base 'scanroot'
$outside = Join-Path $Base 'outside'
$prefixSibling = Join-Path $Base 'scanroot-extra'

New-Item -ItemType Directory -Path (Join-Path $scan 'docs\nested') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $scan 'data') -Force | Out-Null
New-Item -ItemType Directory -Path $outside -Force | Out-Null
New-Item -ItemType Directory -Path $prefixSibling -Force | Out-Null

Set-Content -LiteralPath (Join-Path $scan 'docs\readme.txt') -Value 'readme' -NoNewline
Set-Content -LiteralPath (Join-Path $scan 'docs\nested\deep.txt') -Value 'deep' -NoNewline
Set-Content -LiteralPath (Join-Path $scan 'data\sample.bin') -Value 'binary-ish' -NoNewline
Set-Content -LiteralPath (Join-Path $scan 'plain.txt') -Value 'plain' -NoNewline
Set-Content -LiteralPath (Join-Path $outside 'secret.txt') -Value 'secret' -NoNewline
Set-Content -LiteralPath (Join-Path $prefixSibling 'other.txt') -Value 'other' -NoNewline

New-Item -ItemType Junction -Path (Join-Path $scan 'link-in') -Target (Join-Path $scan 'docs') | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scan 'link-out') -Target $outside | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scan 'link-prefix') -Target $prefixSibling | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scan 'link-loop') -Target $scan | Out-Null

$mklinkOut = cmd.exe /c "cd /d `"$scan`" && mklink /D link-rel docs 2>&1"
Write-Host "mklink link-rel -> $mklinkOut"

$danglingOut = cmd.exe /c "cd /d `"$scan`" && mklink /D link-dangling missing-target 2>&1"
Write-Host "mklink link-dangling -> $danglingOut"

Import-Module (Join-Path $ModuleRoot 'WReparse\WReparse.psd1') -Force

Write-Host ''
Write-Host '=== reparse inventory (raw provider view) ==='
Get-ChildItem -LiteralPath $scan -Force | ForEach-Object {
    $isReparse = [bool]($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
    Write-Host ("  {0,-14} container={1,-5} reparse={2,-5} linkType={3,-13} target={4}" -f `
            $_.Name, $_.PSIsContainer, $isReparse, $_.LinkType, $_.Target)
}

Write-Host ''
Write-Host '=== Get-WReparseReport (Follow = Never) ==='
$report = Get-WReparseReport -Root $scan
ConvertTo-WReparseJson -Report $report

Write-Host ''
Write-Host '=== Get-WReparseReport (Follow = Always) : errors only ==='
$followReport = Get-WReparseReport -Root $scan -Follow
$followReport.Errors | ForEach-Object { Write-Host ("  {0,-16} {1}" -f $_.Code, $_.RelativePath) }
Write-Host ("  records={0} skipped={1}" -f $followReport.Records.Count, $followReport.Stats.Skipped)

Write-Host ''
Write-Host '=== determinism check (two runs byte-identical) ==='
$a = ConvertTo-WReparseJson -Report (Get-WReparseReport -Root $scan)
$b = ConvertTo-WReparseJson -Report (Get-WReparseReport -Root $scan)
Write-Host ("  identical={0}" -f ($a -ceq $b))
