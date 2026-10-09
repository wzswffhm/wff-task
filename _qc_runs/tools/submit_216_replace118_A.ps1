# submit_216_replace118.ps1 —— 用 wfflab__wchunk-216 v1.1.0 替换飞书 118 号（原 217）附件
#
# 权限顺序（不可颠倒）：记录在状态变为「待质检」的瞬间即失去标注员写权限，
# 故：清空旧附件 -> 上传新 zip -> 上传两张新截图 -> 读回校验 -> 改文本字段 -> 最后才改状态。
#
# 段 A：附件替换（状态保持「待提交」，失败可重跑）

[CmdletBinding()]
param(
    [switch]$ConfirmWrite
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if (-not $ConfirmWrite) { throw 'Re-run with -ConfirmWrite.' }

$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg'
$TableId   = 'tblRDxcGkblflMBA'
$RecordId  = 'reczz28KQU8reW2k'
$Repo      = 'C:\Users\Administrator\Desktop\wff-task'
$Deliver   = Join-Path $Repo 'deliverables\2026-10-10_wchunk216-交付'
$ZipPath   = Join-Path $Deliver 'package\wfflab__wchunk-216-v1.1.0-delivery.zip'
$ImgCtl    = Join-Path $Deliver 'evidence\images\oracle_nop_controls.png'
$ImgScore  = Join-Path $Deliver 'evidence\images\score_summary.png'

foreach ($p in @($ZipPath, $ImgCtl, $ImgScore)) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "missing: $p" }
}

function Invoke-LarkJson([string[]]$Arguments) {
    $raw = (& lark-cli @Arguments 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "lark-cli failed: $raw" }
    $s = $raw.IndexOf('{'); $e = $raw.LastIndexOf('}')
    if ($s -lt 0 -or $e -lt $s) { throw "Invalid lark-cli JSON: $raw" }
    return ($raw.Substring($s, $e - $s + 1) | ConvertFrom-Json)
}

function Get-Cells {
    $r = Invoke-LarkJson @('base', '+record-get', '--as', 'user', '--base-token', $BaseToken,
        '--table-id', $TableId, '--record-id', $RecordId, '--format', 'json')
    $fields = @($r.data.fields); $row = @($r.data.data)[0]
    $cells = @{}
    for ($i = 0; $i -lt $fields.Count; $i++) {
        $cells[$fields[$i]] = if ($i -lt $row.Count) { $row[$i] } else { $null }
    }
    return $cells
}

# 0) 状态必须是「待提交」
$cells = Get-Cells
$current = @($cells['状态']) -join ','
Write-Host "current status : $current"
if ($current -ne '待提交') {
    throw "状态为「$current」，标注员此时无写权限。请先在飞书界面改回「待提交」再运行。"
}
Write-Host "old zip        : " ((@($cells['作业压缩包']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', ')
Write-Host "old score img  : " ((@($cells['分数截图']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', ')
Write-Host "old ctl img    : " ((@($cells['oracle/nop截图']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', ')

# 1) 清空三个附件字段（先删旧再传新，避免同名冲突）
Invoke-LarkJson @('base', '+record-upsert', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--json', '{"作业压缩包":[],"分数截图":[],"oracle/nop截图":[]}', '--format', 'json') | Out-Null
Write-Host 'cleared : 作业压缩包 / 分数截图 / oracle-nop截图'

# 2) 上传 zip（lark-cli 限制相对路径 = cwd 内，故 cd 到 package）
Push-Location (Split-Path -Parent $ZipPath)
try {
    Invoke-LarkJson @('base', '+record-upload-attachment', '--as', 'user', '--base-token', $BaseToken,
        '--table-id', $TableId, '--record-id', $RecordId,
        '--field-id', 'fldnki9xts', '--file', (Split-Path -Leaf $ZipPath), '--format', 'json') | Out-Null
} finally { Pop-Location }
Write-Host "uploaded zip    : $(Split-Path -Leaf $ZipPath)"

# 3) 上传两张截图
Push-Location (Split-Path -Parent $ImgCtl)
try {
    Invoke-LarkJson @('base', '+record-upload-attachment', '--as', 'user', '--base-token', $BaseToken,
        '--table-id', $TableId, '--record-id', $RecordId,
        '--field-id', 'fldg4yePGJ', '--file', (Split-Path -Leaf $ImgScore), '--format', 'json') | Out-Null
    Invoke-LarkJson @('base', '+record-upload-attachment', '--as', 'user', '--base-token', $BaseToken,
        '--table-id', $TableId, '--record-id', $RecordId,
        '--field-id', 'fldZI4BCU2', '--file', (Split-Path -Leaf $ImgCtl), '--format', 'json') | Out-Null
} finally { Pop-Location }
Write-Host "uploaded imgs   : $(Split-Path -Leaf $ImgScore), $(Split-Path -Leaf $ImgCtl)"

# 4) 读回校验
$cells = Get-Cells
$expected = Get-Item -LiteralPath $ZipPath
$zipOk = @(@($cells['作业压缩包']) | Where-Object { $_.name -eq $expected.Name -and [int64]$_.size -eq $expected.Length }).Count -gt 0
$scoreOk = @(@($cells['分数截图']) | Where-Object { $_.name -eq 'score_summary.png' }).Count -gt 0
$ctlOk = @(@($cells['oracle/nop截图']) | Where-Object { $_.name -eq 'oracle_nop_controls.png' }).Count -gt 0
[ordered]@{
    status   = (@($cells['状态']) -join ',')
    zip_ok   = $zipOk
    score_ok = $scoreOk
    ctl_ok   = $ctlOk
    zip      = (@($cells['作业压缩包']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    score    = (@($cells['分数截图']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    ctl      = (@($cells['oracle/nop截图']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
} | ConvertTo-Json -Depth 10

if (-not ($zipOk -and $scoreOk -and $ctlOk)) { throw 'read-back verification failed' }
Write-Host 'SECTION_A_OK'
