[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TaskPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$ArchiveName = '',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$task = (Resolve-Path -LiteralPath $TaskPath).Path
$taskId = Split-Path -Leaf $task
$required = @('task.toml', 'source.json', 'instruction.md', 'environment', 'tests', 'solution')
foreach ($name in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $task $name))) { throw "Missing required local task component: $name" }
}

$validator = Join-Path $PSScriptRoot 'validate_requirement_conformance.py'
$validation = (& python -X utf8 $validator --task-path $task 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "Requirements conformance validation failed:`n$validation" }

$taskToml = Get-Content -LiteralPath (Join-Path $task 'task.toml') -Raw
$source = Get-Content -LiteralPath (Join-Path $task 'source.json') -Raw | ConvertFrom-Json
$version = if ($source.task_version) { [string]$source.task_version } elseif ($taskToml -match '(?ms)^\[task\]\s*(.*?)(?=^\[|\z)' -and $Matches[1] -match '(?m)^\s*version\s*=\s*["'']([^"'']+)["'']') { $Matches[1] } else { 'unversioned' }
if (-not $ArchiveName) { $ArchiveName = "$taskId-v$version.zip" }
if (-not $ArchiveName.EndsWith('.zip', [StringComparison]::OrdinalIgnoreCase)) { $ArchiveName += '.zip' }

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$output = Join-Path (Resolve-Path -LiteralPath $OutputDirectory).Path $ArchiveName
if (Test-Path -LiteralPath $output) {
    if (-not $Force) { throw "Output already exists: $output" }
    Remove-Item -LiteralPath $output -Force
}

$stageRoot = Join-Path ([IO.Path]::GetTempPath()) ("generate-win-package-" + [Guid]::NewGuid().ToString('N'))
$stageTask = Join-Path $stageRoot $taskId
New-Item -ItemType Directory -Force -Path $stageTask | Out-Null
try {
    Copy-Item -LiteralPath (Join-Path $task 'task.toml') -Destination $stageTask
    Copy-Item -LiteralPath (Join-Path $task 'instruction.md') -Destination $stageTask
    foreach ($tree in @('environment', 'tests')) {
        $destination = Join-Path $stageTask $tree
        New-Item -ItemType Directory -Force -Path $destination | Out-Null
        & robocopy (Join-Path $task $tree) $destination /E /XD .git TestResults results .nuget-packages node_modules __pycache__ solution evidence runs output tmp /XF .env.local *.user *.suo *.tmp *.log Thumbs.db .DS_Store | Out-Null
        if ($LASTEXITCODE -gt 7) { throw "robocopy failed for $tree with exit code $LASTEXITCODE" }
        $global:LASTEXITCODE = 0
    }

    # Remove ordinary build-output directories while preserving the bundled Go
    # runtime required by native Windows verification.
    $allowedBinRoot = 'environment\assets\go\bin'
    Get-ChildItem -LiteralPath $stageTask -Recurse -Directory -Force |
        Where-Object { $_.Name -in @('bin', 'obj') } |
        Sort-Object { $_.FullName.Length } -Descending |
        ForEach-Object {
            $relative = $_.FullName.Substring($stageTask.Length).TrimStart('\')
            if (-not $relative.Equals($allowedBinRoot, [StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
            }
        }

    $forbiddenComponents = @('solution', 'evidence', 'results', 'runs', 'output', 'tmp', '.git', 'bin', 'obj', 'TestResults', '.nuget-packages', 'node_modules', '__pycache__')
    $forbiddenFiles = @('.env.local', 'Thumbs.db', '.DS_Store')
    $violations = @()
    foreach ($item in Get-ChildItem -LiteralPath $stageTask -Recurse -Force) {
        $relative = $item.FullName.Substring($stageTask.Length).TrimStart('\')
        $parts = $relative -split '[\\/]'
        $underAllowedBin = $relative.Equals($allowedBinRoot, [StringComparison]::OrdinalIgnoreCase) -or
            $relative.StartsWith($allowedBinRoot + '\', [StringComparison]::OrdinalIgnoreCase)
        $forbiddenForItem = if ($underAllowedBin) {
            @($forbiddenComponents | Where-Object { $_ -ne 'bin' })
        } else {
            $forbiddenComponents
        }
        if (@($parts | Where-Object { $forbiddenForItem -contains $_ }).Count -gt 0) { $violations += $relative; continue }
        if ($forbiddenFiles -contains $item.Name -or $item.Extension -in @('.user', '.suo', '.tmp', '.log')) { $violations += $relative }
    }
    if ($violations.Count -gt 0) { throw "Forbidden package content:`n$($violations -join "`n")" }

    $top = @(Get-ChildItem -LiteralPath $stageTask -Force | Select-Object -ExpandProperty Name | Sort-Object)
    $expected = @('environment', 'instruction.md', 'task.toml', 'tests')
    if (($top -join '|') -ne ($expected -join '|')) { throw "Unexpected task-root shape: $($top -join ', ')" }

    Compress-Archive -LiteralPath $stageTask -DestinationPath $output -CompressionLevel Optimal
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash.ToLowerInvariant()
    $result = [ordered]@{
        task_id = $taskId
        version = $version
        zip = $output
        size = (Get-Item -LiteralPath $output).Length
        sha256 = $hash
        top_level = $top
    }
    $result | ConvertTo-Json -Depth 5
    $global:LASTEXITCODE = 0
}
finally {
    if ((Test-Path -LiteralPath $stageRoot) -and $stageRoot.StartsWith([IO.Path]::GetTempPath(), [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
}
