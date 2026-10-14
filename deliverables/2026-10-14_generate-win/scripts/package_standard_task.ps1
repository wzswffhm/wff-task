[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TaskPath,
    [Parameter(Mandatory = $true)]
    [string]$SummaryPath,
    [Parameter(Mandatory = $true)]
    [string]$EvidenceDirectory,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$ArchiveName = '',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$task = (Resolve-Path -LiteralPath $TaskPath).Path
$summaryFile = (Resolve-Path -LiteralPath $SummaryPath).Path
$evidence = (Resolve-Path -LiteralPath $EvidenceDirectory).Path
$taskId = Split-Path -Leaf $task

$validator = Join-Path $PSScriptRoot 'validate_requirement_conformance.py'
$validation = (& python -X utf8 $validator --task-path $task 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "Requirements conformance validation failed:`n$validation" }

$required = @(
    'task.toml', 'source.json', 'instruction.md', 'environment', 'tests', 'solution',
    'environment\adapter.toml', 'environment\Dockerfile', 'environment\prepare.ps1',
    'environment\validate_environment.ps1', 'environment\run.ps1', 'environment\restore.ps1',
    'environment\cleanup.ps1', 'tests\test.ps1', 'tests\run_tests.ps1',
    'tests\aggregate_results.ps1', 'tests\judge.toml', 'tests\rubric.json',
    'solution\README.md', 'solution\solve.ps1'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $task $relative))) {
        throw "Missing standard Task component: $relative"
    }
}

$source = Get-Content -LiteralPath (Join-Path $task 'source.json') -Raw -Encoding utf8 | ConvertFrom-Json
$taskToml = Get-Content -LiteralPath (Join-Path $task 'task.toml') -Raw -Encoding utf8
$taskVersion = if ($source.task_version) { [string]$source.task_version } elseif ($taskToml -match '(?m)^\s*version\s*=\s*"([^"]+)"\s*$') { $Matches[1] } else { throw 'Unable to resolve task version.' }
if ([string]$source.task_id -ne $taskId) { throw 'source.json task_id does not match task directory.' }
foreach ($field in @('source_type', 'source_document', 'license', 'lineage', 'pollution_risk', 'authorization')) {
    if ([string]::IsNullOrWhiteSpace([string]$source.$field)) { throw "source.json is missing provenance field: $field" }
}
if ($taskToml -notmatch '(?m)^\[task\]\s*$' -or $taskToml -notmatch '(?m)^\[policy\]\s*$') {
    throw 'task.toml must include the local runner [task] and [policy] compatibility sections.'
}

$summary = Get-Content -LiteralPath $summaryFile -Raw -Encoding utf8 | ConvertFrom-Json
if ([string]$summary.task_id -ne $taskId) { throw 'Qualification summary task_id does not match task directory.' }
if (-not $summary.gates.qualified) { throw 'Qualification summary is not qualified.' }
if (@($summary.task_versions | Where-Object { [string]$_ -ne $taskVersion }).Count -gt 0) { throw 'Qualification summary contains another task version.' }

$selected = @()
$selected += @($summary.controls.no_change)
$selected += @($summary.controls.golden)
foreach ($model in @('QWEN', 'OPUS', 'GLM', 'KIMI')) { $selected += @($summary.models.$model.selected) }
if ($selected.Count -ne 14) { throw "Expected 14 selected control/model runs, found $($selected.Count)." }

$workspaceRoot = (Resolve-Path (Join-Path $task '..\..')).Path
$runRoot = Join-Path $workspaceRoot ('runs\' + $taskId)
foreach ($run in $selected) {
    if ([string]$run.verdict -notin @('0', '1')) { throw "Invalid selected verdict for run $($run.run_id)." }
    $resultPath = [IO.Path]::GetFullPath([string]$run.result_path)
    if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) { throw "Selected result missing: $resultPath" }
    if (-not $resultPath.StartsWith($runRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Selected result is outside runs root: $resultPath" }
    $result = Get-Content -LiteralPath $resultPath -Raw -Encoding utf8 | ConvertFrom-Json
    if ([string]$result.task_id -ne $taskId -or [string]$result.task_version -ne $taskVersion) { throw "Selected result identity mismatch: $resultPath" }
}

if (-not (Test-Path -LiteralPath (Join-Path $evidence 'oracle_nop_controls.png'))) { throw 'Missing oracle_nop_controls.png.' }
if (-not (Test-Path -LiteralPath (Join-Path $evidence 'score_summary.png'))) { throw 'Missing score_summary.png.' }

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$outputRoot = (Resolve-Path -LiteralPath $OutputDirectory).Path
if (-not $ArchiveName) { $ArchiveName = "$taskId-v$taskVersion-standard.zip" }
if (-not $ArchiveName.EndsWith('.zip', [StringComparison]::OrdinalIgnoreCase)) { $ArchiveName += '.zip' }
$output = Join-Path $outputRoot $ArchiveName
if (Test-Path -LiteralPath $output) {
    if (-not $Force) { throw "Output already exists: $output" }
    Remove-Item -LiteralPath $output -Force
}

$stageRoot = Join-Path ([IO.Path]::GetTempPath()) ('generate-win-standard-' + [Guid]::NewGuid().ToString('N'))
$stageTask = Join-Path $stageRoot $taskId
New-Item -ItemType Directory -Force -Path $stageTask | Out-Null
try {
    foreach ($rootFile in @('task.toml', 'source.json', 'instruction.md')) {
        Copy-Item -LiteralPath (Join-Path $task $rootFile) -Destination (Join-Path $stageTask $rootFile)
    }
    foreach ($tree in @('environment', 'tests', 'solution')) {
        Copy-Item -LiteralPath (Join-Path $task $tree) -Destination (Join-Path $stageTask $tree) -Recurse -Force
    }

    $outside = Join-Path $stageTask 'outside_harbor'
    $extras = Join-Path $stageTask 'delivery-extras'
    foreach ($dir in @($outside, (Join-Path $extras 'source'), (Join-Path $extras 'hashes'), (Join-Path $extras 'original-runs'), (Join-Path $extras 'model_runs'), (Join-Path $extras 'evidence'))) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }

    Copy-Item -LiteralPath (Join-Path $task 'source.json') -Destination (Join-Path $extras 'source\source.json')
    $sourceHash = (Get-FileHash -LiteralPath (Join-Path $task 'source.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    $lineage = [ordered]@{
        task_id = $taskId
        task_version = $taskVersion
        source_json_sha256 = $sourceHash
        source = $source
        generated_at = [DateTimeOffset]::Now.ToString('o')
    }
    $lineage | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $extras 'source\lineage.json') -Encoding utf8

    Copy-Item -LiteralPath $summaryFile -Destination (Join-Path $extras 'model_runs\qualification-summary.json')
    foreach ($model in @('QWEN', 'OPUS', 'GLM', 'KIMI')) {
        $summary.models.$model | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $extras ("model_runs\$model.json")) -Encoding utf8
    }

    foreach ($image in @('oracle_nop_controls.png', 'score_summary.png')) {
        Copy-Item -LiteralPath (Join-Path $evidence $image) -Destination (Join-Path $extras ("evidence\$image"))
    }

    foreach ($run in $selected) {
        $resultPath = [IO.Path]::GetFullPath([string]$run.result_path)
        $runSource = Split-Path -Parent $resultPath
        $runDest = Join-Path $extras ("original-runs\$($run.run_id)\$($run.run_label)")
        New-Item -ItemType Directory -Force -Path $runDest | Out-Null
        foreach ($name in @('result.json', 'test.log', 'verifier.log', 'test-results.json', 'setup.log', 'environment.json')) {
            $candidate = Join-Path $runSource $name
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { Copy-Item -LiteralPath $candidate -Destination (Join-Path $runDest $name) }
        }
    }

    $deliveryManifest = [ordered]@{
        schema_version = 'standard-task-delivery-v1'
        task_id = $taskId
        task_version = $taskVersion
        qualification_summary = 'delivery-extras/model_runs/qualification-summary.json'
        selected_run_count = $selected.Count
        package_scope = @('complete-task', 'outside_harbor', 'delivery-extras')
        generated_at = [DateTimeOffset]::Now.ToString('o')
    }
    $deliveryManifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $extras 'delivery-manifest.json') -Encoding utf8

    $files = @(Get-ChildItem -LiteralPath $stageTask -Recurse -File -Force | ForEach-Object {
        [ordered]@{ path = $_.FullName.Substring($stageTask.Length + 1).Replace('\', '/'); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(); size = $_.Length }
    })
    $import = [ordered]@{
        schema_version = 'outside-harbor-import-v1'
        task_id = $taskId
        task_version = $taskVersion
        source_repo = [string]$source.repo
        source_commit = [string]$source.commit
        source_json_sha256 = $sourceHash
        participant_entrypoint = 'environment/run.ps1'
        verifier_entrypoint = 'tests/run_tests.ps1'
        rubric = 'tests/rubric.json'
        files = $files
        generated_at = [DateTimeOffset]::Now.ToString('o')
    }
    $import | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $outside 'import.json') -Encoding utf8

    $manifestLines = @()
    Get-ChildItem -LiteralPath $stageTask -Recurse -File -Force | Where-Object { $_.FullName -ne (Join-Path $extras 'hashes\manifest.sha256') } | ForEach-Object {
        $relative = $_.FullName.Substring($stageTask.Length + 1).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $manifestLines += "$hash  $relative"
    }
    $manifestLines | Sort-Object | Set-Content -LiteralPath (Join-Path $extras 'hashes\manifest.sha256') -Encoding ascii

    Compress-Archive -LiteralPath $stageTask -DestinationPath $output -CompressionLevel Optimal
    [ordered]@{ task_id = $taskId; version = $taskVersion; zip = $output; size = (Get-Item -LiteralPath $output).Length; sha256 = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant(); selected_runs = $selected.Count } | ConvertTo-Json -Depth 10
    $global:LASTEXITCODE = 0
}
finally {
    if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
}
