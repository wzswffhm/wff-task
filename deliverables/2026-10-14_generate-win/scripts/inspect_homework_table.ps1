[CmdletBinding()]
param(
    [string]$BaseToken = 'EsJebL8JJaf7g4sIbItcnMFgnvg',
    [string]$TableId = 'tblRDxcGkblflMBA',
    [string]$CandidateTitle = '',
    [string]$CandidateDirection = '',
    [string]$CandidatePrompt = '',
    [string]$CandidateSourceIdentity = '',
    [double]$SimilarityThreshold = 0.56,
    [string]$OutputPath = '',
    [switch]$FailOnDuplicate
)

$ErrorActionPreference = 'Stop'

function Normalize-Text([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
    $text = [System.Net.WebUtility]::HtmlDecode($Value)
    $text = $text -replace '<br\s*/?>', ' '
    $text = $text.ToLowerInvariant()
    $text = $text -replace '[\p{P}\p{S}\s]+', ' '
    return ($text -replace '\s+', ' ').Trim()
}

function Get-Heading([string]$Prompt) {
    if ([string]::IsNullOrWhiteSpace($Prompt)) { return '' }
    foreach ($line in ($Prompt -split "`r?`n")) {
        if ($line -match '^\s*#{1,6}\s+(.+?)\s*$') { return $Matches[1] }
    }
    return (($Prompt -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 1) -replace '^\s*[-*]+\s*', '')
}

function Get-Shingles([string]$Value, [int]$Width = 3) {
    $normalized = (Normalize-Text $Value) -replace '\s', ''
    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    if ($normalized.Length -eq 0) { return $set }
    if ($normalized.Length -le $Width) { [void]$set.Add($normalized); return $set }
    for ($i = 0; $i -le $normalized.Length - $Width; $i++) {
        [void]$set.Add($normalized.Substring($i, $Width))
    }
    return $set
}

function Get-Jaccard([string]$Left, [string]$Right) {
    $a = Get-Shingles $Left
    $b = Get-Shingles $Right
    if ($a.Count -eq 0 -or $b.Count -eq 0) { return 0.0 }
    $intersection = 0
    foreach ($item in $a) { if ($b.Contains($item)) { $intersection++ } }
    $union = $a.Count + $b.Count - $intersection
    if ($union -eq 0) { return 0.0 }
    return [Math]::Round($intersection / $union, 4)
}

$arguments = @(
    'base', '+record-list', '--as', 'user',
    '--base-token', $BaseToken,
    '--table-id', $TableId,
    '--field-id', '题目方向',
    '--field-id', '提示词',
    '--field-id', '状态',
    '--format', 'json'
)
$raw = (& lark-cli @arguments 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "lark-cli record-list failed: $raw" }
$response = $raw | ConvertFrom-Json -Depth 100
if (-not $response.ok) { throw "Feishu record-list returned ok=false: $raw" }

$records = @()
$fields = @($response.data.fields)
$rows = @($response.data.data)
$ids = @($response.data.record_id_list)
for ($i = 0; $i -lt $rows.Count; $i++) {
    $row = @($rows[$i])
    $record = [ordered]@{ record_id = $ids[$i] }
    for ($column = 0; $column -lt $fields.Count; $column++) {
        $record[$fields[$column]] = if ($column -lt $row.Count) { $row[$column] } else { $null }
    }
    $prompt = [string]$record['提示词']
    $title = Get-Heading $prompt
    $promptSimilarity = Get-Jaccard $CandidatePrompt $prompt
    $titleSimilarity = Get-Jaccard $CandidateTitle $title
    $directionMatch = (Normalize-Text $CandidateDirection) -ne '' -and (Normalize-Text $CandidateDirection) -eq (Normalize-Text ([string]$record['题目方向']))
    $sourceMatch = (Normalize-Text $CandidateSourceIdentity) -ne '' -and (Normalize-Text $prompt).Contains((Normalize-Text $CandidateSourceIdentity))
    $duplicate = $sourceMatch -or ($promptSimilarity -ge $SimilarityThreshold) -or ($titleSimilarity -ge 0.75 -and $directionMatch)
    $record['title'] = $title
    $record['prompt_similarity'] = $promptSimilarity
    $record['title_similarity'] = $titleSimilarity
    $record['direction_match'] = $directionMatch
    $record['source_identity_match'] = $sourceMatch
    $record['is_duplicate'] = $duplicate
    $records += [pscustomobject]$record
}

$matches = @($records | Where-Object { $_.is_duplicate } | Sort-Object prompt_similarity, title_similarity -Descending)
$result = [ordered]@{
    checked_at = [DateTimeOffset]::Now.ToString('o')
    base_token_configured = -not [string]::IsNullOrWhiteSpace($BaseToken)
    table_id = $TableId
    record_count = $records.Count
    candidate = [ordered]@{
        title = $CandidateTitle
        direction = $CandidateDirection
        source_identity = $CandidateSourceIdentity
        similarity_threshold = $SimilarityThreshold
    }
    duplicate = ($matches.Count -gt 0)
    matches = $matches
    records = $records
}
$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $json | Set-Content -LiteralPath $OutputPath -Encoding utf8
}
$json
if ($FailOnDuplicate -and $matches.Count -gt 0) { exit 10 }
