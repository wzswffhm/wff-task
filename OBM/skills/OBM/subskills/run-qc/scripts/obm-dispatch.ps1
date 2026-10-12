[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('qc', 'run')]
    [string]$Action,

    [string[]]$InputPath,

    [ValidateRange(1, 100)]
    [int]$Count = 1,

    [string]$ConfigFile
)

$ErrorActionPreference = 'Stop'
$bundleRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ConfigFile)) {
    $ConfigFile = Join-Path $bundleRoot 'config\obm.paths.json'
}
$exampleConfig = Join-Path $bundleRoot 'config\obm.paths.example.json'
if (-not (Test-Path -LiteralPath $ConfigFile)) {
    throw "Missing config file: $ConfigFile. Copy obm.paths.example.json to obm.paths.json and edit it."
}
$cfg = Get-Content -LiteralPath $ConfigFile -Raw -Encoding utf8 | ConvertFrom-Json

function Get-ConfiguredPath([string]$Value, [string]$Fallback) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $Fallback }
    return $Value
}

$obmRoot = Get-ConfiguredPath ([string]$cfg.obm_root) 'D:\hc\obm'
$cacheDir = Get-ConfiguredPath ([string]$cfg.cache_dir) (Join-Path $obmRoot 'cache')
$resultDir = Get-ConfiguredPath ([string]$cfg.result_dir) (Join-Path $obmRoot 'result')
$qcDir = Get-ConfiguredPath ([string]$cfg.qc_tool_dir) (Join-Path $obmRoot '质检工具\obm-review-skills')
$governing = Get-ConfiguredPath ([string]$cfg.governing_document) (Join-Path $obmRoot '需求\OBM Source 收集说明书-正式.md')
$benchmarkWorkspace = Get-ConfiguredPath ([string]$cfg.benchmark_workspace) (Join-Path $cacheDir 'benchmark-workspaces')
$benchmarkConfig = Get-ConfiguredPath ([string]$cfg.benchmark_config) (Join-Path $benchmarkWorkspace 'benchmark-locations.local.json')
$validator = Join-Path $qcDir 'scripts\validate_proposals.py'
$inventory = Join-Path $qcDir 'scripts\obm_inventory.py'
$manifestTool = Join-Path $qcDir 'scripts\sha256_manifest.py'
foreach ($required in @($qcDir, $cacheDir, $resultDir, $validator)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing configured path: $required" }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dispatchDir = Join-Path $cacheDir "dispatch\$stamp"
New-Item -ItemType Directory -Path $dispatchDir -Force | Out-Null

function Invoke-Validator([string]$Target, [string]$OutputDir) {
    $report = Join-Path $OutputDir 'validator-report.json'
    $lines = & python $validator --json $Target 2>&1
    $code = $LASTEXITCODE
    $lines | Set-Content -LiteralPath $report -Encoding utf8
    return [pscustomobject]@{ code = $code; report = $report; output = ($lines -join "`n") }
}

function Invoke-QcTarget([string]$Target, [string]$Label) {
    $safe = ($Label -replace '[^A-Za-z0-9._-]', '_')
    $out = Join-Path $dispatchDir $safe
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    $result = [ordered]@{ target = $Target; label = $Label; validator = $null; inventory = $null; manifest = $null; errors = @() }
    try {
        $v = Invoke-Validator $Target $out
        $result.validator = [ordered]@{ exit_code = $v.code; report = $v.report }
        if ($v.code -ne 0) { $result.errors += 'validate_proposals.py failed' }

        if (Test-Path -LiteralPath $inventory) {
            $invDir = Join-Path $out 'inventory'
            New-Item -ItemType Directory -Path $invDir -Force | Out-Null
            $args = @('--root', $Target, '--workspace', $benchmarkWorkspace, '--output-dir', $invDir)
            if (Test-Path -LiteralPath $benchmarkConfig) { $args += @('--config', $benchmarkConfig) }
            if (Test-Path -LiteralPath $governing) { $args += @('--governing-document', $governing) }
            if (Test-Path -LiteralPath $v.report) { $args += @('--upstream-report', $v.report) }
            $invLog = Join-Path $out 'inventory.log'
            & python $inventory @args 2>&1 | Tee-Object -FilePath $invLog
            $result.inventory = [ordered]@{ exit_code = $LASTEXITCODE; output_dir = $invDir; log = $invLog }
            if ($LASTEXITCODE -ne 0) { $result.errors += 'obm_inventory.py failed' }
        }

        if (Test-Path -LiteralPath $manifestTool) {
            $manifest = Join-Path $out 'SHA256SUMS'
            & python $manifestTool --output $manifest --base $Target $Target 2>&1 | Tee-Object -FilePath (Join-Path $out 'manifest.log')
            $result.manifest = [ordered]@{ exit_code = $LASTEXITCODE; path = $manifest }
            if ($LASTEXITCODE -ne 0) { $result.errors += 'sha256_manifest.py failed' }
        }
    }
    catch {
        $result.errors += $_.Exception.Message
    }
    $resultFile = Join-Path $out 'qc-summary.json'
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $resultFile -Encoding utf8
    return [pscustomobject]$result
}

function Get-ZipProposalRoot([string]$ZipPath, [string]$ExtractRoot) {
    $name = [IO.Path]::GetFileNameWithoutExtension($ZipPath)
    $dest = Join-Path $ExtractRoot ($name -replace '[^A-Za-z0-9._-]', '_')
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $dest -Force
    $proposal = Get-ChildItem -LiteralPath $dest -Recurse -File -Filter 'proposal.json' | Select-Object -First 1
    if ($null -eq $proposal) { throw "No proposal.json found in $ZipPath" }
    return $proposal.Directory.FullName
}

function Get-QcTargets {
    $targets = @()
    if ($InputPath) {
        foreach ($p in $InputPath) {
            $resolved = (Resolve-Path -LiteralPath $p -ErrorAction Stop).Path
            if ((Get-Item -LiteralPath $resolved).PSIsContainer) {
                $proposal = Get-ChildItem -LiteralPath $resolved -Recurse -File -Filter 'proposal.json' | Select-Object -First 1
                $targets += [pscustomobject]@{ path = if ($proposal) { $proposal.Directory.FullName } else { $resolved }; label = (Split-Path $resolved -Leaf) }
            }
            elseif ([IO.Path]::GetExtension($resolved) -ieq '.zip') {
                $extract = Join-Path $dispatchDir 'extract'
                New-Item -ItemType Directory -Path $extract -Force | Out-Null
                $root = Get-ZipProposalRoot $resolved $extract
                $targets += [pscustomobject]@{ path = $root; label = [IO.Path]::GetFileNameWithoutExtension($resolved) }
            }
            else { throw "Unsupported QC input: $resolved" }
        }
    }
    else {
        foreach ($dir in Get-ChildItem -LiteralPath $resultDir -Directory -ErrorAction SilentlyContinue) {
            $proposal = Get-ChildItem -LiteralPath $dir.FullName -Recurse -File -Filter 'proposal.json' | Select-Object -First 1
            if ($proposal) { $targets += [pscustomobject]@{ path = $proposal.Directory.FullName; label = $dir.Name } }
        }
        foreach ($zip in Get-ChildItem -LiteralPath $resultDir -File -Filter '*.zip' -ErrorAction SilentlyContinue) {
            if ($zip.BaseName -like 'obm-run-qc-bundle*') { continue }
            try {
                $extract = Join-Path $dispatchDir 'extract'
                New-Item -ItemType Directory -Path $extract -Force | Out-Null
                $root = Get-ZipProposalRoot $zip.FullName $extract
                $targets += [pscustomobject]@{ path = $root; label = $zip.BaseName }
            } catch { Write-Warning $_.Exception.Message }
        }
    }
    return $targets
}

function Test-FrozenCandidate([string]$Candidate) {
    $sumFile = Join-Path $Candidate 'evidence\freeze\SHA256SUMS'
    if (-not (Test-Path -LiteralPath $sumFile)) { return $false }
    foreach ($line in Get-Content -LiteralPath $sumFile) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split '\s+', 2
        if ($parts.Count -ne 2) { return $false }
        $file = Join-Path $Candidate $parts[1]
        if (-not (Test-Path -LiteralPath $file)) { return $false }
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLowerInvariant() -ne $parts[0].ToLowerInvariant()) { return $false }
    }
    return $true
}

function Get-NextAttempt([string]$Candidate) {
    $dyn = Join-Path $Candidate 'evidence\dynamic'
    $max = 0
    if (Test-Path -LiteralPath $dyn) {
        foreach ($d in Get-ChildItem -LiteralPath $dyn -Directory -Filter 'attempt-*') {
            if ($d.Name -match '^attempt-(\d+)$') { $max = [Math]::Max($max, [int]$Matches[1]) }
        }
    }
    return ('attempt-{0:D3}' -f ($max + 1))
}

function Get-RunCandidates {
    $found = @()
    if ($InputPath) {
        foreach ($p in $InputPath) {
            $c = (Resolve-Path -LiteralPath $p -ErrorAction Stop).Path
            if (-not (Test-Path (Join-Path $c 'run-trae-arm.ps1'))) { throw "Not a runnable candidate: $c" }
            $found += Get-Item -LiteralPath $c
        }
    }
    else {
        $runRoot = Join-Path $cacheDir 'runs'
        if (Test-Path -LiteralPath $runRoot) {
            $found = Get-ChildItem -LiteralPath $runRoot -Directory -Recurse | Where-Object {
                (Test-Path (Join-Path $_.FullName 'run-trae-arm.ps1')) -and (Test-Path (Join-Path $_.FullName 'evidence\freeze\SHA256SUMS'))
            } | Sort-Object LastWriteTime
        }
    }
    return @($found | Select-Object -First $Count)
}

if ($Action -eq 'qc') {
    $targets = @(Get-QcTargets)
    if ($targets.Count -eq 0) { Write-Output "No proposal package found under $resultDir"; exit 2 }
    $all = foreach ($t in $targets) { Invoke-QcTarget $t.path $t.label }
    $all | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $dispatchDir 'dispatch-summary.json') -Encoding utf8
    $all | Format-Table label, @{n='validator';e={$_.validator.exit_code}}, @{n='inventory';e={if($_.inventory){$_.inventory.exit_code}else{'n/a'}}}, @{n='errors';e={$_.errors.Count}} -AutoSize
    Write-Output "Reports: $dispatchDir"
    exit 0
}

$context = (& docker context show).Trim()
$serverOs = (& docker version --format '{{.Server.Os}}').Trim()
if ($context -ne 'desktop-linux' -or $serverOs -ne 'linux') { throw "Docker must use desktop-linux/linux; got $context/$serverOs" }
$candidates = @(Get-RunCandidates)
if ($candidates.Count -eq 0) { Write-Output 'No runnable frozen candidate found.'; exit 2 }
$runResults = @()
foreach ($candidate in $candidates) {
    if (-not (Test-FrozenCandidate $candidate.FullName)) {
        $runResults += [pscustomobject]@{ candidate = $candidate.FullName; status = 'freeze_mismatch'; attempt = $null }
        continue
    }
    $attempt = Get-NextAttempt $candidate.FullName
    $runner = Join-Path $candidate.FullName ([string]$cfg.runner_script_name)
    $runnerArgs = @('-Mode', 'no-skill', '-Attempt', $attempt)
    if ($cfg.runner_image) { $runnerArgs += @('-RunnerImage', [string]$cfg.runner_image) }
    if ($cfg.task_image) { $runnerArgs += @('-TaskImage', [string]$cfg.task_image) }
    $console = Join-Path $dispatchDir (($candidate.Name) + '-' + $attempt + '.log')
    $runnerCode = 0
    $runnerError = $null
    try {
        & $runner @runnerArgs 2>&1 | Tee-Object -FilePath $console
        $runnerCode = $LASTEXITCODE
    }
    catch {
        $runnerCode = 1
        $runnerError = $_.Exception.Message
        $_ | Out-File -LiteralPath $console -Append -Encoding utf8
    }
    $arm = Join-Path $candidate.FullName ("evidence\dynamic\$attempt\no-skill")
    $runFile = Join-Path $arm 'run-result.json'
    $run = if (Test-Path $runFile) { Get-Content $runFile -Raw | ConvertFrom-Json } else { $null }
    $infra = $runnerCode -ne 0 -or (Test-Path $console -and (Select-String -LiteralPath $console -Pattern 'AccountQuotaExceeded|Docker.*500|infrastructure' -Quiet))
    $entry = [ordered]@{ candidate = $candidate.FullName; attempt = $attempt; no_skill_exit_code = $runnerCode; no_skill = $run; with_skill = $null; runner_error = $runnerError; infrastructure_interruption = $infra }
    if (-not $infra -and $run -and -not [bool]$run.solved -and [int]$run.turns -ge [int]$cfg.min_no_skill_turns) {
        $withArgs = @('-Mode', 'with-skill', '-Attempt', $attempt)
        if ($cfg.runner_image) { $withArgs += @('-RunnerImage', [string]$cfg.runner_image) }
        if ($cfg.task_image) { $withArgs += @('-TaskImage', [string]$cfg.task_image) }
        $withLog = Join-Path $dispatchDir (($candidate.Name) + '-' + $attempt + '-with-skill.log')
        try { & $runner @withArgs 2>&1 | Tee-Object -FilePath $withLog }
        catch { $_ | Out-File -LiteralPath $withLog -Append -Encoding utf8 }
        $withArm = Join-Path $candidate.FullName ("evidence\dynamic\$attempt\with-skill\run-result.json")
        if (Test-Path $withArm) { $entry.with_skill = Get-Content $withArm -Raw | ConvertFrom-Json }
    }
    $runResults += [pscustomobject]$entry
}
$runResults | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $dispatchDir 'dispatch-summary.json') -Encoding utf8
$runResults | Select-Object candidate,attempt,no_skill_exit_code,infrastructure_interruption | Format-Table -AutoSize
Write-Output "Reports: $dispatchDir"
