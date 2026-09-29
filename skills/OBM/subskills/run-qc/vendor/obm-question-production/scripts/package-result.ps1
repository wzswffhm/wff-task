[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir,

    [Parameter(Mandatory = $true)]
    [string]$QualityDecision,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]*$')]
    [string]$ProposalName,

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$TaskId,

    [Parameter(Mandatory = $true)]
    [string]$FinalScreenshot,

    [string]$ResultDir,

    [string]$CacheDir,

    [switch]$Replace
)

$ErrorActionPreference = 'Stop'

function Assert-Condition {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Resolve-EvidencePath {
    param([string]$Value, [string]$DecisionDirectory)
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }
    return Join-Path $DecisionDirectory $Value
}

$skillRoot = Split-Path -Parent $PSScriptRoot
$obmRoot = [System.IO.Path]::GetFullPath((Join-Path $skillRoot '..\..'))
if ([string]::IsNullOrWhiteSpace($ResultDir)) {
    $ResultDir = Join-Path $obmRoot 'result'
}
if ([string]::IsNullOrWhiteSpace($CacheDir)) {
    $CacheDir = Join-Path $obmRoot 'cache'
}

$resolvedProject = (Resolve-Path -LiteralPath $ProjectDir).Path
$resolvedDecision = (Resolve-Path -LiteralPath $QualityDecision).Path
$decisionDirectory = Split-Path -Parent $resolvedDecision
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
$cacheRoot = (Resolve-Path -LiteralPath $CacheDir).Path

$validator = Join-Path $PSScriptRoot 'validate-proposal.ps1'
$validationJson = & $validator -ProjectDir $resolvedProject
$validation = $validationJson | ConvertFrom-Json
Assert-Condition ($validation.status -eq 'pass') 'Candidate structure validation did not pass.'

try {
    $quality = Get-Content -LiteralPath $resolvedDecision -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
}
catch {
    throw "quality-decision.json is not valid JSON: $($_.Exception.Message)"
}

foreach ($field in @('candidate_id', 'decision', 'reviewer', 'reviewed_at', 'artifacts', 'gates', 'quality_incentive', 'evidence')) {
    Assert-Condition ($quality.Contains($field)) "Quality decision is missing '$field'."
}
Assert-Condition ($quality.decision -eq 'pass') 'Quality decision is not pass.'
Assert-Condition ($quality.reviewer -is [string] -and -not [string]::IsNullOrWhiteSpace($quality.reviewer)) 'Quality decision must identify an independent reviewer or harness.'
$reviewedAt = [datetimeoffset]::MinValue
Assert-Condition ([datetimeoffset]::TryParse([string]$quality.reviewed_at, [ref]$reviewedAt)) 'reviewed_at must be an ISO-8601 timestamp.'
Assert-Condition ($quality.artifacts -is [System.Collections.IDictionary]) 'artifacts must be an object.'
Assert-Condition ($quality.gates -is [System.Collections.IDictionary]) 'gates must be an object.'
Assert-Condition ($quality.quality_incentive -is [System.Collections.IDictionary]) 'quality_incentive must be an object.'
Assert-Condition ($quality.evidence -is [System.Collections.IDictionary]) 'evidence must be an object.'
foreach ($hashName in @('proposal_sha256', 'delivery_sha256')) {
    Assert-Condition ($quality.artifacts.Contains($hashName)) "Quality decision is missing artifacts.$hashName."
    Assert-Condition ([string]$quality.artifacts[$hashName] -match '^[0-9a-fA-F]{64}$') "artifacts.$hashName must be a SHA-256 hash."
}
Assert-Condition ([string]$quality.artifacts.proposal_sha256 -eq [string]$validation.proposal_sha256) 'proposal.json changed after quality approval.'
Assert-Condition ([string]$quality.artifacts.delivery_sha256 -eq [string]$validation.delivery_sha256) 'The delivery tree changed after quality approval.'

$requiredAcceptanceGates = @('format', 'content_relevance', 'originality', 'solvability', 'verifier_quality', 'anti_leakage')
foreach ($gate in $requiredAcceptanceGates) {
    Assert-Condition ($quality.gates.Contains($gate) -and $quality.gates[$gate] -eq 'pass') "Quality gate '$gate' is not pass."
}

foreach ($softGate in @('baseline_value', 'skill_effect')) {
    if ($quality.gates.Contains($softGate)) {
        Assert-Condition ([string]$quality.gates[$softGate] -in @('pass', 'not_met', 'inconclusive', 'not_run')) "Quality target '$softGate' has an invalid status."
    }
}

Assert-Condition ($quality.quality_incentive.Contains('status')) 'quality_incentive.status is required.'
Assert-Condition ([string]$quality.quality_incentive.status -in @('met', 'not_met', 'inconclusive', 'not_run')) 'quality_incentive.status must be met, not_met, inconclusive, or not_run.'

if ($quality.Contains('runs')) {
    Assert-Condition ($quality.runs -is [System.Collections.IDictionary]) 'runs must be an object when present.'
    foreach ($runName in @('no_skill', 'with_skill')) {
        if (-not $quality.runs.Contains($runName)) { continue }
        Assert-Condition ($quality.runs[$runName] -is [System.Collections.IDictionary]) "runs.$runName must be an object."
        foreach ($field in @('solved', 'turns', 'duration_seconds')) {
            Assert-Condition ($quality.runs[$runName].Contains($field)) "Quality decision is missing runs.$runName.$field."
        }
        Assert-Condition ($quality.runs[$runName].solved -is [bool]) "runs.$runName.solved must be a boolean."
        Assert-Condition ($quality.runs[$runName].turns -is [ValueType] -and [double]$quality.runs[$runName].turns -ge 0) "runs.$runName.turns must be non-negative."
        Assert-Condition ($quality.runs[$runName].duration_seconds -is [ValueType] -and [double]$quality.runs[$runName].duration_seconds -ge 0) "runs.$runName.duration_seconds must be non-negative."
    }
}

Assert-Condition ($quality.evidence.Contains('static_review')) 'Quality decision is missing evidence.static_review.'
foreach ($evidenceName in @('static_review', 'no_skill_run', 'with_skill_run', 'verifier_report')) {
    if (-not $quality.evidence.Contains($evidenceName)) { continue }
    $evidenceValue = [string]$quality.evidence[$evidenceName]
    Assert-Condition (-not [string]::IsNullOrWhiteSpace($evidenceValue)) "evidence.$evidenceName must not be empty."
    $evidencePath = Resolve-EvidencePath -Value $evidenceValue -DecisionDirectory $decisionDirectory
    $resolvedEvidence = [System.IO.Path]::GetFullPath($evidencePath)
    Assert-Condition ($resolvedEvidence.StartsWith($cacheRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) "evidence.$evidenceName must be stored under CacheDir."
    Assert-Condition (Test-Path -LiteralPath $evidencePath) "Evidence path does not exist: $evidencePath"
}

$resolvedScreenshot = (Resolve-Path -LiteralPath $FinalScreenshot).Path
Assert-Condition ($resolvedScreenshot.StartsWith($cacheRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) 'FinalScreenshot must be stored under CacheDir before packaging.'
$screenshotExtension = [System.IO.Path]::GetExtension($resolvedScreenshot).ToLowerInvariant()
Assert-Condition ($screenshotExtension -in @('.png', '.jpg', '.jpeg', '.webp')) 'FinalScreenshot must be PNG, JPG, JPEG, or WEBP.'

$proposal = Get-Content -LiteralPath (Join-Path $resolvedProject 'proposal.json') -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
$packageName = "$($proposal.benchmark)_$ProposalName"
$sourcesReadme = Join-Path $resolvedProject 'sources\README.md'
Assert-Condition (Test-Path -LiteralPath $sourcesReadme -PathType Leaf) 'sources/README.md is required in the delivery package.'
if ([string]::IsNullOrWhiteSpace($TaskId)) {
    $TaskId = [string]$quality.candidate_id
}
Assert-Condition ($TaskId -match '^[A-Za-z0-9][A-Za-z0-9._-]*$') 'TaskId must contain only letters, numbers, dot, underscore, and hyphen.'
New-Item -ItemType Directory -Force -Path $ResultDir, $CacheDir | Out-Null
$resultRoot = (Resolve-Path -LiteralPath $ResultDir).Path
$targetTaskDirectory = Join-Path $resultRoot $TaskId

$stagingRoot = Join-Path $cacheRoot (Join-Path 'package-staging' ([guid]::NewGuid().ToString('N')))
$archiveStaging = Join-Path $stagingRoot 'archive'
$resultTaskStaging = Join-Path $stagingRoot (Join-Path 'result' $TaskId)
$outerDirectory = Join-Path $archiveStaging $packageName
New-Item -ItemType Directory -Force -Path $outerDirectory, $resultTaskStaging | Out-Null
$zipPath = Join-Path $resultTaskStaging "$packageName.zip"
$screenshotName = "final-qc$screenshotExtension"
$stagedScreenshot = Join-Path $resultTaskStaging $screenshotName

try {
    Copy-Item -LiteralPath (Join-Path $resolvedProject 'proposal.json') -Destination $outerDirectory -Force
    Copy-Item -LiteralPath (Join-Path $resolvedProject 'sources') -Destination $outerDirectory -Recurse -Force
    Copy-Item -LiteralPath $resolvedScreenshot -Destination $stagedScreenshot -Force
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $archiveStaging,
        $zipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entries = @($archive.Entries | Where-Object { -not [string]::IsNullOrEmpty($_.Name) })
        Assert-Condition ($entries.Count -eq ([int]$validation.source_file_count + 1)) 'Package file count differs from the validated source tree; a hidden file may be missing.'
        Assert-Condition (@($entries.FullName | Select-Object -Unique).Count -eq $entries.Count) 'Package contains duplicate entries.'
        $prefix = "$packageName/"
        foreach ($entry in $entries) {
            $normalized = $entry.FullName.Replace('\', '/')
            Assert-Condition ($normalized.StartsWith($prefix, [System.StringComparison]::Ordinal)) "Archive entry is outside the required outer folder: $normalized"
            $relative = $normalized.Substring($prefix.Length)
            Assert-Condition ($relative -eq 'proposal.json' -or $relative.StartsWith('sources/', [System.StringComparison]::Ordinal)) "Unexpected archive entry: $normalized"
        }
        Assert-Condition (@($entries | Where-Object { $_.FullName.Replace('\', '/') -eq "$prefix`proposal.json" }).Count -eq 1) 'Archive must contain exactly one proposal.json.'
        Assert-Condition (@($entries | Where-Object { $_.FullName.Replace('\', '/').StartsWith("$prefix`sources/", [System.StringComparison]::Ordinal) }).Count -gt 0) 'Archive sources directory is empty.'
        Assert-Condition (@($entries | Where-Object { $_.FullName.Replace('\', '/') -eq "$prefix`sources/README.md" }).Count -eq 1) 'Archive must contain sources/README.md.'
    }
    finally {
        $archive.Dispose()
    }

    $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $screenshotHash = (Get-FileHash -LiteralPath $stagedScreenshot -Algorithm SHA256).Hash.ToLowerInvariant()
    $readmePath = Join-Path $resultTaskStaging 'README.md'
    @(
        "# OBM delivery $TaskId",
        '',
        "- Task ID: $TaskId",
        "- Package: $packageName.zip",
        "- Benchmark: $($proposal.benchmark)",
        "- Candidate ID: $($quality.candidate_id)",
        "- Quality decision: $($quality.decision)",
        "- Acceptance basis: data-quality item 1",
        "- Quality-incentive item 2: $($quality.quality_incentive.status)",
        "- Reviewer: $($quality.reviewer)",
        "- Reviewed at: $($quality.reviewed_at)",
        "- Final QC screenshot: $screenshotName",
        "- Package SHA-256: $zipHash"
    ) | Set-Content -LiteralPath $readmePath -Encoding UTF8
    $readmeHash = (Get-FileHash -LiteralPath $readmePath -Algorithm SHA256).Hash.ToLowerInvariant()
    @(
        "$zipHash  $packageName.zip",
        "$screenshotHash  $screenshotName",
        "$readmeHash  README.md"
    ) | Set-Content -LiteralPath (Join-Path $resultTaskStaging 'SHA256SUMS') -Encoding ASCII

    if (Test-Path -LiteralPath $targetTaskDirectory) {
        Assert-Condition ([bool]$Replace) "Result task directory already exists: $targetTaskDirectory. Use -Replace to archive it under cache and create a new result."
        $backupDirectory = Join-Path $cacheRoot 'package-backups'
        New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null
        $backupName = "$TaskId-$([datetime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))"
        Move-Item -LiteralPath $targetTaskDirectory -Destination (Join-Path $backupDirectory $backupName)
    }
    Move-Item -LiteralPath $resultTaskStaging -Destination $targetTaskDirectory
}
catch {
    throw
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}

$finalZipPath = Join-Path $targetTaskDirectory "$packageName.zip"
$finalScreenshotPath = Join-Path $targetTaskDirectory $screenshotName
$finalReadmePath = Join-Path $targetTaskDirectory 'README.md'
$zipHash = (Get-FileHash -LiteralPath $finalZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
[pscustomobject]@{
    status = 'packaged'
    task_id = $TaskId
    result_directory = $targetTaskDirectory
    package = $finalZipPath
    screenshot = $finalScreenshotPath
    readme = $finalReadmePath
    manifest = (Join-Path $targetTaskDirectory 'SHA256SUMS')
    sha256 = $zipHash
    candidate_id = $quality.candidate_id
    quality_incentive = $quality.quality_incentive.status
    reviewer = $quality.reviewer
} | ConvertTo-Json -Depth 4
