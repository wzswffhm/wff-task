#Requires -Version 5.1
<#
.SYNOPSIS
    Frozen-input fingerprint for the two Harbor images of task windows-d4-litemonitor-001.

.DESCRIPTION
    Both images build independently from the digest-pinned Microsoft SDK.
    This additional fingerprint checks frozen agent-visible task inputs.
    Dockerfile.scorer is excluded because it embeds the expected fingerprint.
    Tests, solution and delivery evidence are excluded from the agent identity.

.PARAMETER TaskDir
    Root of the task package. Defaults to the parent of this script's directory.

.PARAMETER OutPath
    Where -Write stores the stamp. Defaults to $env:HARBOR_IMAGE_STAMP or C:\harbor\image_stamp.json.

.OUTPUTS
    Exit code 0 = stamp written, or assertion held.
    Exit code 2 = assertion failed, or the frozen inputs could not be hashed (infrastructure fault).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\image_stamp.ps1 -Write
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\image_stamp.ps1 -Assert 9f2c...
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)][string]$TaskDir,
    [Parameter(Mandatory = $false)][string]$OutPath,
    [Parameter(Mandatory = $false)][switch]$Write,
    [Parameter(Mandatory = $false)][string]$Assert = ''
)

$ErrorActionPreference = 'Stop'

if (-not $TaskDir) { $TaskDir = Split-Path -Parent $PSScriptRoot }
$TaskDir = (Resolve-Path -LiteralPath $TaskDir).ProviderPath

if (-not $OutPath) {
    $OutPath = [string]$env:HARBOR_IMAGE_STAMP
    if (-not $OutPath) { $OutPath = 'C:\harbor\image_stamp.json' }
}

# Relative paths use forward slashes so the digest is identical on every host and in every
# container regardless of the platform separator. Comparison is ordinal and case-sensitive.
$ExcludedRelative = @('environment/dockerfile.scorer')
$ExcludedTopLevel = @('tests', 'solution', 'metadata', 'evidence', 'jobs')

function Get-RelativePath {
    param([string]$Root, [string]$Full)
    $rel = $Full.Substring($Root.Length).TrimStart('\', '/')
    return ($rel -replace '\\', '/')
}

function Get-FrozenInputFingerprint {
    param([string]$Root)
    $prefix = $Root.Length + 1
    $entries = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force)) {
        $full = $file.FullName
        if ($full.Length -le $prefix) { continue }
        $rel = Get-RelativePath -Root $Root -Full $full
        $top = ($rel -split '/')[0].ToLowerInvariant()
        if ($ExcludedTopLevel -contains $top) { continue }
        if ($ExcludedRelative -contains $rel.ToLowerInvariant()) { continue }
        $hash = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
        $entries += [pscustomobject]@{ rel = $rel; sha256 = $hash; bytes = $file.Length }
    }
    $sorted = @($entries | Sort-Object -Property @{ Expression = 'rel'; Ascending = $true })
    $payload = New-Object System.Text.StringBuilder
    foreach ($item in $sorted) {
        [void]$payload.Append($item.rel)
        [void]$payload.Append("`n")
        [void]$payload.Append($item.sha256)
        [void]$payload.Append("`n")
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = [System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($payload.ToString())))
    }
    finally { $sha.Dispose() }
    $fingerprint = ($digest -replace '-', '').ToLowerInvariant()
    return [pscustomobject]@{ fingerprint = $fingerprint; file_count = $sorted.Count; entries = $sorted }
}

$stamp = Get-FrozenInputFingerprint -Root $TaskDir

if ($Assert) {
    $expected = $Assert.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{64}$') {
        Write-Host "IMAGE_STAMP_ASSERT=FAILED (the asserted value '$expected' is not a 64-character lowercase sha256 hex digest)"
        exit 2
    }
    if ($stamp.fingerprint -ne $expected) {
        Write-Host "IMAGE_STAMP_ASSERT=FAILED"
        Write-Host "  inherited Agent image frozen-input fingerprint : $($stamp.fingerprint)"
        Write-Host "  fingerprint frozen into Dockerfile.scorer        : $expected"
        Write-Host '  The Scorer image may only be built on top of the Agent image whose frozen agent-visible'
        Write-Host '  inputs (instruction.md, task.toml, environment/**) produced the asserted digest. Rebuild'
        Write-Host '  Dockerfile.scorer against the current Agent image instead of overriding this check.'
        exit 2
    }
    Write-Host "IMAGE_STAMP_ASSERT=OK fingerprint=$($stamp.fingerprint) files=$($stamp.file_count)"
    exit 0
}

if (-not $Write) {
    Write-Host "IMAGE_STAMP_FINGERPRINT=$($stamp.fingerprint)"
    Write-Host "IMAGE_STAMP_FILES=$($stamp.file_count)"
    exit 0
}

$payload = [ordered]@{
    schema_version      = 'harbor.image_stamp/v1'
    task_id             = 'windows-d4-litemonitor-001'
    image_role          = 'agent'
    fingerprint_algo    = 'sha256 over sorted "relpath\nsha256\n" records of every frozen agent-visible input'
    fingerprint         = $stamp.fingerprint
    frozen_input_files  = $stamp.file_count
    included_roots      = @('instruction.md', 'task.toml', 'environment/')
    excluded_paths      = (@('environment/Dockerfile.scorer') + ($ExcludedTopLevel | ForEach-Object { "$_/" }))
    exclusion_reason    = 'Dockerfile.scorer embeds this fingerprint so it cannot be an input to it; tests/ solution/ metadata/ evidence/ are never copied into the Agent image, and excluding them is what makes the host-side and in-container digests identical.'
    entries             = @($stamp.entries | ForEach-Object { [ordered]@{ path = $_.rel; sha256 = $_.sha256; bytes = $_.bytes } })
    created_at_utc      = [DateTime]::UtcNow.ToString('o')
}
$json = ($payload | ConvertTo-Json -Depth 8)
$parent = Split-Path -Parent $OutPath
if ($parent -and -not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
[System.IO.File]::WriteAllText($OutPath, $json, (New-Object System.Text.UTF8Encoding $false))
Write-Host "IMAGE_STAMP_WRITTEN=$OutPath"
Write-Host "IMAGE_STAMP_FINGERPRINT=$($stamp.fingerprint)"
Write-Host "IMAGE_STAMP_FILES=$($stamp.file_count)"
exit 0
