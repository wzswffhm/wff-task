# upload_zip_no_status.ps1
#
# 只上传「作业压缩包」附件，**绝不修改「状态」字段**。
#
# 背景：本表在状态被置为「待质检」后，标注员立即失去该记录的写权限，
# 附件就再也传不上去了（215 的 _feishu_upload.log 里 exit=99 就是这个原因）。
# 因此上传必须在状态为「待提交」时进行，且上传动作本身不改状态 —— 状态由人工改。
#
# 用法：
#   .\upload_zip_no_status.ps1 -ZipPath <zip> -RecordId <rec...> -ConfirmWrite

[CmdletBinding()]
param(
    [string]$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg',
    [string]$TableId   = 'tblRDxcGkblflMBA',
    [Parameter(Mandatory = $true)][string]$RecordId,
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [switch]$KeepExisting,      # 保留旧附件（默认先清空，只留新包）
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

$before = Get-Cells
$statusBefore = @($before['状态']) -join ','
Write-Host "record        : $RecordId"
Write-Host "status before : $statusBefore   (本脚本不会修改它)"
if ($statusBefore -ne '待提交') {
    Write-Warning "状态不是「待提交」；标注员此时可能没有写权限，上传大概率会被拒。"
}

if (-not $KeepExisting) {
    try {
        Invoke-LarkJson @('base', '+record-upsert', '--as', 'user', '--base-token', $BaseToken,
            '--table-id', $TableId, '--record-id', $RecordId,
            '--json', '{"作业压缩包":[]}', '--format', 'json') | Out-Null
        Write-Host 'cleared       : 作业压缩包（旧附件已移除）'
    } catch {
        Write-Warning "清空旧附件失败（将直接追加新包）：$($_.Exception.Message)"
    }
}

Invoke-LarkJson @('base', '+record-upload-attachment', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--field-id', 'fldnki9xts', '--file', $ZipPath, '--format', 'json') | Out-Null
Write-Host "uploaded      : $(Split-Path -Leaf $ZipPath)"

$after = Get-Cells
$statusAfter = @($after['状态']) -join ','
$atts = @($after['作业压缩包'])
Write-Host ("zip field     : " + (($atts | ForEach-Object { "$($_.name)($($_.size))" }) -join ', '))
Write-Host "status after  : $statusAfter"

$expected = Get-Item -LiteralPath $ZipPath
$ok = @($atts | Where-Object { $_.name -eq $expected.Name -and [int64]$_.size -eq $expected.Length }).Count -gt 0
if (-not $ok) { throw 'read-back did not find the uploaded zip with the expected name/size.' }
if ($statusAfter -ne $statusBefore) { throw "状态字段被意外修改：$statusBefore -> $statusAfter" }

[ordered]@{
    record_id     = $RecordId
    zip           = "$($expected.Name)($($expected.Length))"
    status_before = $statusBefore
    status_after  = $statusAfter
    status_untouched = $true
    verified      = $true
} | ConvertTo-Json -Depth 6
