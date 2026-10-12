# 读取飞书任意记录的当前字段（只读）。
# 用法: pwsh -NoProfile -File query_feishu_record.ps1 -RecordId recxxxx [-Full]
param(
    [Parameter(Mandatory = $true)][string]$RecordId,
    [switch]$Full
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:LARK_CLI_NO_PROXY = '1'

$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg'
$TableId   = 'tblRDxcGkblflMBA'

$raw = (& lark-cli base +record-get --as user --base-token $BaseToken --table-id $TableId `
        --record-id $RecordId --format json 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "lark-cli failed: $raw" }
$s = $raw.IndexOf('{'); $e = $raw.LastIndexOf('}')
$doc = $raw.Substring($s, $e - $s + 1) | ConvertFrom-Json

$fields = @($doc.data.fields)
$row = @($doc.data.data)[0]
Write-Output ("record_id = {0}   fields = {1}" -f $RecordId, $fields.Count)
for ($i = 0; $i -lt $fields.Count; $i++) {
    $name = $fields[$i]
    $value = if ($i -lt $row.Count) { $row[$i] } else { $null }
    if ($null -eq $value) { Write-Output ("  {0,-16} <empty>" -f $name); continue }
    if ($value -is [System.Array] -and $value.Count -gt 0 -and $value[0].PSObject.Properties.Name -contains 'name') {
        $files = ($value | ForEach-Object { "{0}({1}B)" -f $_.name, $_.size }) -join ', '
        Write-Output ("  {0,-16} [附件] {1}" -f $name, $files)
        continue
    }
    $text = ($value | ConvertTo-Json -Compress -Depth 6)
    $limit = if ($Full) { 100000 } else { 200 }
    if ($text.Length -gt $limit) { $text = $text.Substring(0, $limit) + '…' }
    Write-Output ("  {0,-16} {1}" -f $name, $text)
}
