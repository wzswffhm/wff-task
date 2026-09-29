[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir
)

$ErrorActionPreference = 'Stop'

function Assert-Condition {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Assert-ExactKeys {
    param(
        [System.Collections.IDictionary]$Object,
        [string[]]$Required,
        [string[]]$Optional = @(),
        [string]$Location
    )

    $actual = @($Object.Keys)
    foreach ($key in $Required) {
        Assert-Condition ($actual -contains $key) "$Location is missing required key '$key'."
    }
    $allowed = @($Required) + @($Optional)
    foreach ($key in $actual) {
        Assert-Condition ($allowed -contains $key) "$Location contains unexpected key '$key'."
    }
}

function Assert-Text {
    param([object]$Value, [string]$Location)
    Assert-Condition ($Value -is [string] -and -not [string]::IsNullOrWhiteSpace($Value)) "$Location must be a non-empty string."
}

function Get-DeliveryHash {
    param([string]$Root, [string]$ProposalFile, [string]$SourcesDirectory)

    $files = @((Get-Item -LiteralPath $ProposalFile)) + @(Get-ChildItem -LiteralPath $SourcesDirectory -Recurse -File -Force)
    $records = foreach ($file in $files | Sort-Object FullName) {
        $relative = [System.IO.Path]::GetRelativePath($Root, $file.FullName).Replace('\', '/')
        $fileHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$relative`t$($file.Length)`t$fileHash"
    }
    $payload = [System.Text.Encoding]::UTF8.GetBytes(($records -join "`n") + "`n")
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return [System.Convert]::ToHexString($algorithm.ComputeHash($payload)).ToLowerInvariant()
    }
    finally {
        $algorithm.Dispose()
    }
}

$resolvedProject = (Resolve-Path -LiteralPath $ProjectDir).Path
$proposalPath = Join-Path $resolvedProject 'proposal.json'
$sourcesPath = Join-Path $resolvedProject 'sources'

Assert-Condition (Test-Path -LiteralPath $proposalPath -PathType Leaf) "Missing proposal.json in $resolvedProject."
Assert-Condition (Test-Path -LiteralPath $sourcesPath -PathType Container) "Missing sources directory in $resolvedProject."
Assert-Condition (@(Get-ChildItem -LiteralPath $sourcesPath -Recurse -File -Force).Count -gt 0) 'sources must contain at least one file.'

$topLevelEntries = @(Get-ChildItem -LiteralPath $resolvedProject -Force)
foreach ($entry in $topLevelEntries) {
    Assert-Condition ($entry.Name -in @('proposal.json', 'sources')) "Unexpected top-level delivery entry '$($entry.Name)'."
}

try {
    $proposal = Get-Content -LiteralPath $proposalPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
}
catch {
    throw "proposal.json is not valid JSON: $($_.Exception.Message)"
}

Assert-Condition ($proposal -is [System.Collections.IDictionary]) 'proposal.json root must be an object.'
$rootKeys = @(
    'benchmark', 'domain', 'related_question', 'proposal_type', 'allow_network',
    'proposal', 'proposal_sources', 'proposal_scene', 'proposal_verify', 'expert_experience_skill'
)
Assert-ExactKeys -Object $proposal -Required $rootKeys -Location 'proposal.json'

$benchmarkValues = @('terminal_bench3', 'terminal_bench4', 'programbench', 'swe_marathon', 'deepSWE', 'froniterSWE')
Assert-Condition ($proposal.benchmark -is [string] -and $proposal.benchmark -in $benchmarkValues) 'benchmark must match the source specification enum.'
Assert-Condition ($proposal.proposal_type -is [string] -and $proposal.proposal_type -in @('A', 'B', 'C')) 'proposal_type must be A, B, or C.'
Assert-Condition ($proposal.allow_network -is [bool]) 'allow_network must be a JSON boolean.'

foreach ($field in @('domain', 'related_question', 'proposal_sources', 'proposal_scene', 'proposal_verify', 'expert_experience_skill')) {
    Assert-Text -Value $proposal[$field] -Location $field
}

$domainParts = @($proposal.domain -split '/')
Assert-Condition ($domainParts.Count -ge 2 -and $domainParts.Count -le 3) 'domain must contain two or three slash-separated levels.'
foreach ($part in $domainParts) {
    Assert-Condition ($part -match '^[A-Za-z0-9][A-Za-z0-9 &.+#()_-]*$') "domain levels must be written in English; invalid level '$part'."
}

Assert-Condition ($proposal.proposal -is [System.Collections.IDictionary]) 'proposal must be an object.'
$requiredProposalKeys = @('A_modification_idea', 'B_modification_details', 'C_agent_task', 'D_task_difficulties')
$difficultyKey = 'D_task_difficulties'
Assert-ExactKeys -Object $proposal.proposal -Required $requiredProposalKeys -Location 'proposal'
foreach ($field in $requiredProposalKeys | Where-Object { $_ -ne $difficultyKey }) {
    Assert-Text -Value $proposal.proposal[$field] -Location "proposal.$field"
}
$difficulties = @($proposal.proposal[$difficultyKey])
Assert-Condition ($proposal.proposal[$difficultyKey] -is [System.Collections.IList] -and $difficulties.Count -gt 0) "proposal.$difficultyKey must be a non-empty array."
for ($index = 0; $index -lt $difficulties.Count; $index++) {
    Assert-Text -Value $difficulties[$index] -Location "proposal.$difficultyKey[$index]"
}

$hash = (Get-FileHash -LiteralPath $proposalPath -Algorithm SHA256).Hash.ToLowerInvariant()
$deliveryHash = Get-DeliveryHash -Root $resolvedProject -ProposalFile $proposalPath -SourcesDirectory $sourcesPath
[pscustomobject]@{
    status = 'pass'
    schema_profile = 'FinalFourField'
    project_dir = $resolvedProject
    proposal_sha256 = $hash
    delivery_sha256 = $deliveryHash
    source_file_count = @(Get-ChildItem -LiteralPath $sourcesPath -Recurse -File -Force).Count
} | ConvertTo-Json -Depth 4
