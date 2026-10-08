# submit_217_correct_order.ps1
#
# 为什么需要这个脚本：upload_feishu.ps1 的顺序是「先 record-upsert 写状态、后 upload-attachment」。
# 但本表在状态被置为「待质检」的那一刻，标注员就失去该记录的写权限 —— 所以后面的附件上传
# 必然 permission_denied（215 当时 exit=99 也是这个原因，不是 scope 问题）。
#
# 正确顺序（本脚本）：
#   1. 确认状态仍是「待提交」（否则退出，先把状态改回来）
#   2. 清空旧「作业压缩包」附件（此时有写权限）
#   3. 上传新 zip
#   4. 读回校验附件只有新包
#   5. 最后才把状态置为「待质检」
#   6. 终检读回

[CmdletBinding()]
param(
    [string]$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg',
    [string]$TableId = 'tblRDxcGkblflMBA',
    [string]$RecordId = 'reczz28KQU8reW2k',
    [string]$ZipPath = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-08_harbor-windows-整改\package\wfflab__wreparse-217-v1.0.0-delivery.zip',
    [string]$Status = '待质检',
    [switch]$ConfirmWrite
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if (-not $ConfirmWrite) { throw 'Re-run with -ConfirmWrite.' }
if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) { throw "zip not found: $ZipPath" }

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

$cells = Get-Cells
$current = @($cells['状态']) -join ','
Write-Host "current status : $current"
if ($current -ne '待提交') {
    throw "状态为「$current」，标注员此时没有写权限。请先在飞书界面把状态改回「待提交」，再运行本脚本。"
}

# 2) 清空旧 zip
Invoke-LarkJson @('base', '+record-upsert', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--json', '{"作业压缩包":[]}', '--format', 'json') | Out-Null
Write-Host 'cleared : 作业压缩包'

# 3) 上传新 zip
Invoke-LarkJson @('base', '+record-upload-attachment', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--field-id', 'fldnki9xts', '--file', $ZipPath, '--format', 'json') | Out-Null
Write-Host "uploaded: $(Split-Path -Leaf $ZipPath)"

# 4) 读回校验
$cells = Get-Cells
$atts = @($cells['作业压缩包'])
Write-Host ("read back: " + (($atts | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '))
$expected = Get-Item -LiteralPath $ZipPath
if (-not (@($atts | Where-Object { $_.name -eq $expected.Name -and [int64]$_.size -eq $expected.Length }).Count -gt 0)) {
    throw 'read-back did not find the uploaded zip with the expected name/size.'
}
if ($atts.Count -ne 1) { Write-Warning "附件字段含 $($atts.Count) 个文件，预期 1 个。" }

# 5) 最后改状态
Invoke-LarkJson @('base', '+record-upsert', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--json', ("{0}" -f (@{ '状态' = @($Status) } | ConvertTo-Json -Compress)), '--format', 'json') | Out-Null
Write-Host "status  : $Status"

# 6) 终检
$cells = Get-Cells
[ordered]@{
    record_id       = $RecordId
    status          = (@($cells['状态']) -join ',')
    direction       = [string]$cells['题目方向']
    zip             = (@($cells['作业压缩包']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    oracle_shot     = (@($cells['oracle/nop截图']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    score_shot      = (@($cells['分数截图']) | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '
    prompt_chars    = ([string]$cells['提示词']).Length
    verified        = $true
} | ConvertTo-Json -Depth 10
