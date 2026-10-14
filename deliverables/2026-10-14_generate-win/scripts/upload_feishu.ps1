[CmdletBinding()]
param(
    [string]$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg',
    [string]$TableId = 'tblRDxcGkblflMBA',
    [string]$RecordId = '',
    [Parameter(Mandatory = $true)]
    [string]$Direction,
    [Parameter(Mandatory = $true)]
    [string]$PromptFile,
    [Parameter(Mandatory = $true)]
    [string]$OracleImage,
    [Parameter(Mandatory = $true)]
    [string]$ScoreImage,
    [Parameter(Mandatory = $true)]
    [string]$ZipPath,
    [ValidateSet('待提交', '待质检', '待返修', '本地质检通过')]
    [string]$Status = '待提交',
    [switch]$ConfirmWrite
)

$ErrorActionPreference = 'Stop'
# zh-CN 主机默认按 GBK 解码原生 stdout，而 lark-cli 输出 UTF-8：不前置编码会让
# 中文字段名变乱码（oracle/nop鎴浘）并使 JSON 解析失败，且此时记录已写入、
# 三个附件全未上传。参见 2026-10-07_wreparse217-交付/FEISHU_WRITEBACK.md。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if (-not $ConfirmWrite) { throw 'Feishu write not confirmed. Re-run with -ConfirmWrite after user authorization.' }
foreach ($path in @($PromptFile, $OracleImage, $ScoreImage, $ZipPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file not found: $path" }
    if ((Get-Item -LiteralPath $path).Length -le 0) { throw "Required file is empty: $path" }
}

function Invoke-LarkJson([string[]]$Arguments) {
    $raw = (& lark-cli @Arguments 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "lark-cli failed: $raw" }
    $start = $raw.IndexOf('{')
    $end = $raw.LastIndexOf('}')
    if ($start -lt 0 -or $end -lt $start) { throw "Invalid lark-cli JSON: $raw" }
    $json = $raw.Substring($start, $end - $start + 1)
    try { return $json | ConvertFrom-Json } catch { throw "Invalid lark-cli JSON: $raw" }
}

function Normalize-Newlines([string]$Value) {
    return (($Value -replace "`r`n", "`n") -replace "`r", "`n").TrimEnd()
}

function Find-RecordId($Value) {
    if ($null -eq $Value) { return $null }
    if ($Value -is [string]) { return $null }
    if ($Value -is [System.Collections.IEnumerable] -and $Value -isnot [pscustomobject]) {
        foreach ($item in $Value) { $found = Find-RecordId $item; if ($found) { return $found } }
        return $null
    }
    foreach ($property in $Value.PSObject.Properties) {
        if ($property.Name -in @('record_id', '_record_id') -and $property.Value) { return [string]$property.Value }
        if ($property.Name -eq 'record_id_list' -and $property.Value) {
            $first = @($property.Value | Where-Object { $_ } | Select-Object -First 1)
            if ($first.Count -gt 0) { return [string]$first[0] }
        }
        $found = Find-RecordId $property.Value
        if ($found) { return $found }
    }
    return $null
}

$prompt = Get-Content -LiteralPath $PromptFile -Raw -Encoding utf8
$payload = [ordered]@{
    '题目方向' = $Direction
    '提示词' = $prompt
    '状态' = @($Status)
}
$upsertArgs = @('base', '+record-upsert', '--as', 'user', '--base-token', $BaseToken, '--table-id', $TableId, '--json', ($payload | ConvertTo-Json -Compress -Depth 10), '--format', 'json')
if ($RecordId) { $upsertArgs += @('--record-id', $RecordId) }
$upsert = Invoke-LarkJson $upsertArgs
if (-not $RecordId) { $RecordId = Find-RecordId $upsert }
if (-not $RecordId) { throw "Unable to resolve record ID from upsert response: $($upsert | ConvertTo-Json -Depth 20)" }

$uploads = @(
    @{ field = 'fldZI4BCU2'; field_name = 'oracle/nop截图'; path = (Resolve-Path -LiteralPath $OracleImage).Path },
    @{ field = 'fldg4yePGJ'; field_name = '分数截图'; path = (Resolve-Path -LiteralPath $ScoreImage).Path },
    @{ field = 'fldnki9xts'; field_name = '作业压缩包'; path = (Resolve-Path -LiteralPath $ZipPath).Path }
)
$existing = Invoke-LarkJson @(
    'base', '+record-get', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--field-id', 'oracle/nop截图', '--field-id', '分数截图', '--field-id', '作业压缩包',
    '--format', 'json'
)
$existingFields = @($existing.data.fields)
$existingRows = @($existing.data.data)
$existingCells = @{}
if ($existingRows.Count -eq 1) {
    $existingRow = @($existingRows[0])
    for ($i = 0; $i -lt $existingFields.Count; $i++) {
        $existingCells[$existingFields[$i]] = if ($i -lt $existingRow.Count) { $existingRow[$i] } else { $null }
    }
}
$uploadResults = @()
foreach ($upload in $uploads) {
    $file = Get-Item -LiteralPath $upload.path
    $alreadyUploaded = @(@($existingCells[$upload.field_name]) | Where-Object {
        $_.name -eq $file.Name -and [int64]$_.size -eq $file.Length
    }).Count -gt 0
    if ($alreadyUploaded) {
        $uploadResults += [pscustomobject]@{ ok = $true; skipped = $true; field = $upload.field; name = $file.Name; size = $file.Length }
    } else {
        $uploadResults += Invoke-LarkJson @(
            'base', '+record-upload-attachment', '--as', 'user',
            '--base-token', $BaseToken, '--table-id', $TableId,
            '--record-id', $RecordId, '--field-id', $upload.field,
            '--file', $upload.path, '--format', 'json'
        )
    }
}

$verify = Invoke-LarkJson @(
    'base', '+record-get', '--as', 'user', '--base-token', $BaseToken,
    '--table-id', $TableId, '--record-id', $RecordId,
    '--field-id', '题目方向', '--field-id', '提示词', '--field-id', '状态',
    '--field-id', 'oracle/nop截图', '--field-id', '分数截图', '--field-id', '作业压缩包',
    '--format', 'json'
)

$verifyFields = @($verify.data.fields)
$verifyRows = @($verify.data.data)
if ($verifyRows.Count -ne 1) { throw "Read-back did not return exactly one record for $RecordId." }
$verifyRow = @($verifyRows[0])
$cells = @{}
for ($i = 0; $i -lt $verifyFields.Count; $i++) {
    $cells[$verifyFields[$i]] = if ($i -lt $verifyRow.Count) { $verifyRow[$i] } else { $null }
}
if ([string]$cells['题目方向'] -ne $Direction) { throw 'Read-back direction does not match the uploaded value.' }
if ((Normalize-Newlines ([string]$cells['提示词'])) -ne (Normalize-Newlines $prompt)) { throw 'Read-back prompt does not match instruction.md.' }
if (@($cells['状态']) -notcontains $Status) { throw 'Read-back status does not match the uploaded value.' }

$attachmentExpectations = @{
    'oracle/nop截图' = (Split-Path -Leaf $OracleImage)
    '分数截图' = (Split-Path -Leaf $ScoreImage)
    '作业压缩包' = (Split-Path -Leaf $ZipPath)
}
foreach ($fieldName in $attachmentExpectations.Keys) {
    $attachments = @($cells[$fieldName])
    $expectedName = $attachmentExpectations[$fieldName]
    $match = @($attachments | Where-Object { $_.name -eq $expectedName -and [int64]$_.size -gt 0 })
    if ($match.Count -eq 0) { throw "Read-back attachment verification failed for $fieldName ($expectedName)." }
}

[ordered]@{
    uploaded_at = [DateTimeOffset]::Now.ToString('o')
    record_id = $RecordId
    direction = $Direction
    status = $Status
    verified = $true
    files = @($uploads | ForEach-Object { [ordered]@{ field_id = $_.field; path = $_.path; size = (Get-Item -LiteralPath $_.path).Length } })
    read_back = $verify
} | ConvertTo-Json -Depth 30
