[CmdletBinding()]
param(
    [string]$OutDir = "C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu"
)

# List all records whose assignee is wff, from the two task-package Bases.
# lark-cli +record-list --format json returns data.data as a 2-D array (rows x cols);
# column order matches the order of --field-id arguments.
# NOTE: keep this file pure ASCII -- PowerShell 5.1 parses .ps1 as ANSI, so non-ASCII
# literals here would be corrupted. Use field IDs instead of field names.

$ErrorActionPreference = 'Stop'
$WFF = 'ou_35041bb28c45c5be1213b2b1af040d90'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Get-Records {
    param([string]$Token, [string]$Table, [string[]]$Fields)
    $cliArgs = @('base', '+record-list', '--base-token', $Token, '--table-id', $Table,
                 '--limit', '200', '--format', 'json', '--as', 'user')
    foreach ($f in $Fields) { $cliArgs += @('--field-id', $f) }
    $raw = (& lark-cli @cliArgs 2>&1 | Out-String)
    return ($raw | ConvertFrom-Json)
}

$targets = @(
    [pscustomobject]@{
        Name   = 'harbor-windows'
        Token  = 'EsJebL8JJaf7g4sIbItcnMFgnvg'
        Table  = 'tblRDxcGkblflMBA'
        # text / assignee / status / job-zip / direction
        Fields = @('fldffCZZex', 'flda4emMz7', 'fldd6UxkAs', 'fldnki9xts', 'fldiuFJbFr')
    },
    [pscustomobject]@{
        Name   = 'harbor-weakness'
        Token  = 'QpzNb4fXSamfX6sLloBcPfHNnug'
        Table  = 'tblPNrBtjFfwOowN'
        # task / assignee / status / task-attachment / deliverable / seq
        Fields = @('fld1bfmLqv', 'fldgADMj3N', 'fldKFzG0cA', 'fldf8Ymaw2', 'fld8TMUhqI', 'fld5kMM38p')
    }
)

foreach ($t in $targets) {
    Write-Host "===== $($t.Name) ====="
    $json = Get-Records -Token $t.Token -Table $t.Table -Fields $t.Fields
    if (-not $json.ok) { Write-Host "  call failed"; continue }
    $rows = @($json.data.data)
    Write-Host "  total=$($rows.Count)  has_more=$($json.data.has_more)"
    ($json | ConvertTo-Json -Depth 25) | Set-Content -Encoding UTF8 (Join-Path $OutDir "$($t.Name).json")

    $hit = 0
    for ($i = 0; $i -lt $rows.Count; $i++) {
        $row = $rows[$i]
        $who = $row[1]
        $ids = @()
        if ($who) { $ids = @($who | ForEach-Object { $_.id }) }
        if ($ids -notcontains $WFF) { continue }
        $hit++
        $name = $row[0]
        $status = if ($row[2]) { (@($row[2]) -join ',') } else { '(empty)' }
        $zip = ''
        if ($t.Name -eq 'harbor-windows') {
            if ($row[3]) { $zip = (@($row[3]) | ForEach-Object { $_.name }) -join ',' }
        }
        else {
            if ($row[4]) { $zip = (@($row[4]) | ForEach-Object { $_.name }) -join ',' }
        }
        Write-Host ("  [{0}] {1} | status={2} | zip={3}" -f $hit, $name, $status, $zip)
    }
    Write-Host "  wff records=$hit"
    Write-Host ""
}
