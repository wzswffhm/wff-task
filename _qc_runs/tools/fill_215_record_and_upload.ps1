# fill_215_record_and_upload.ps1
#
# 为 215 的新建记录补齐文本字段并上传三个附件。
# **不修改「状态」字段**（保持飞书默认/用户设置），上传前后都会核对它没变。
#
# 背景：本表一旦状态变为「待质检」，标注员立即失去写权限、附件再也传不上；
# 因此所有写入都必须在「待提交」状态下完成，且由人工负责改状态。

[CmdletBinding()]
param(
    [string]$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg',
    [string]$TableId   = 'tblRDxcGkblflMBA',
    [string]$RecordId  = 'reczz28KwEOO3xHy',
    [string]$TaskDir   = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wfmt-215',
    [string]$ZipPath   = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-08_harbor-windows-整改\package\wfflab__wfmt-215-v2.0.0-delivery.zip',
    [string]$OracleShot = 'C:\Users\Administrator\Desktop\wff-task1\deliverables\2026-10-07_wfmt215-outside-repair\evidence\oracle_nop_controls.png',
    [string]$ScoreShot  = 'C:\Users\Administrator\Desktop\wff-task1\deliverables\2026-10-07_wfmt215-outside-repair\evidence\score_summary.png',
    [string]$Direction = 'Windows/文件格式与序列化（LEB128 varint + CRC32 容器）/Python/缺陷修复',
    [switch]$ConfirmWrite
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if (-not $ConfirmWrite) { throw 'Re-run with -ConfirmWrite.' }

$promptFile = Join-Path $TaskDir 'instruction.md'
foreach ($p in @($promptFile, $ZipPath, $OracleShot, $ScoreShot)) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "file not found: $p" }
}

function Invoke-LarkJson([string[]]$Arguments) {
    $raw = (& lark-cli @Arguments 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "lark-cli failed: $raw" }
    $s = $raw.IndexOf('{'); $e = $raw.LastIndexOf('}')
    if ($s -lt 0 -or $e -lt $s) { throw "Invalid lark-cli JSON: $raw" }
    return ($raw.Substring($s, $e - $s + 1) | ConvertFrom-Json -Depth 100)
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

$statusBefore = @((Get-Cells)['状态']) -join ','
Write-Host "status before : $statusBefore  (脚本不会修改它)"
if ($statusBefore -ne '待提交') { throw "状态为「$statusBefore」，标注员此时没有写权限，先在界面改回「待提交」。" }

# 1) 文本字段（题目方向 + 提示词）—— 只提交这两个键，状态不在其中
$prompt = Get-Content -LiteralPath $promptFile -Raw -Encoding utf8
$payload = [ordered]@{ '题目方向' = $Direction; '提示词' = $prompt }
Invoke-LarkJson @('base', '+record-upsert', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--json', ($payload | ConvertTo-Json -Compress -Depth 10), '--format', 'json') | Out-Null
Write-Host "written       : 题目方向 + 提示词（$($prompt.Length) 字符）"

# 2) 附件
$uploads = @(
    @{ field = 'fldnki9xts'; name = '作业压缩包';    path = $ZipPath },
    @{ field = 'fldZI4BCU2'; name = 'oracle/nop截图'; path = $OracleShot },
    @{ field = 'fldg4yePGJ'; name = '分数截图';       path = $ScoreShot }
)
foreach ($u in $uploads) {
    Invoke-LarkJson @('base', '+record-upload-attachment', '--as', 'user', '--base-token', $BaseToken,
        '--table-id', $TableId, '--record-id', $RecordId,
        '--field-id', $u.field, '--file', $u.path, '--format', 'json') | Out-Null
    Write-Host "uploaded      : $($u.name) <- $(Split-Path -Leaf $u.path)"
}

# 3) 读回核验
$cells = Get-Cells
$statusAfter = @($cells['状态']) -join ','
if ($statusAfter -ne $statusBefore) { throw "状态字段被意外修改：$statusBefore -> $statusAfter" }
foreach ($u in $uploads) {
    $want = Get-Item -LiteralPath $u.path
    $got = @($cells[$u.name])
    $ok = @($got | Where-Object { $_.name -eq $want.Name -and [int64]$_.size -eq $want.Length }).Count -gt 0
    if (-not $ok) { throw "附件核验失败：$($u.name) 未找到 $($want.Name)($($want.Length))" }
}
if ([string]$cells['题目方向'] -ne $Direction) { throw '题目方向读回不一致' }

[ordered]@{
    record_id        = $RecordId
    direction        = [string]$cells['题目方向']
    prompt_chars     = ([string]$cells['提示词']).Length
    zip              = (@($cells['作业压缩包'])    | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    oracle_shot      = (@($cells['oracle/nop截图']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    score_shot       = (@($cells['分数截图'])       | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    status_before    = $statusBefore
    status_after     = $statusAfter
    status_untouched = $true
    verified         = $true
} | ConvertTo-Json -Depth 6
