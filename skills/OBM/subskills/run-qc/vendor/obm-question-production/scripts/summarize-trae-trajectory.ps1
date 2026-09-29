[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TrajectoryFile,

    [string]$OutputFile
)

$ErrorActionPreference = 'Stop'

$resolvedTrajectory = (Resolve-Path -LiteralPath $TrajectoryFile).Path
$trajectory = Get-Content -LiteralPath $resolvedTrajectory -Raw | ConvertFrom-Json

$agentSteps = @($trajectory.agent_steps)
$llmInteractions = @($trajectory.llm_interactions)
$maxStepNumber = 0
if ($agentSteps.Count -gt 0) {
    $maxStepNumber = [int](($agentSteps | Measure-Object -Property step_number -Maximum).Maximum)
}

$summary = [ordered]@{
    schema_version = '1.0'
    trajectory_path = $resolvedTrajectory
    trajectory_sha256 = (Get-FileHash -LiteralPath $resolvedTrajectory -Algorithm SHA256).Hash.ToLowerInvariant()
    provider = $trajectory.provider
    model = $trajectory.model
    configured_max_steps = [int]$trajectory.max_steps
    turns = $agentSteps.Count
    max_step_number = $maxStepNumber
    llm_interactions = $llmInteractions.Count
    start_time = $trajectory.start_time
    end_time = $trajectory.end_time
    duration_seconds = [double]$trajectory.execution_time
    agent_reported_success = [bool]$trajectory.success
    verifier_status = 'not_evaluated'
}

$json = $summary | ConvertTo-Json -Depth 4
if ($OutputFile) {
    $outputParent = Split-Path -Parent $OutputFile
    if ($outputParent -and -not (Test-Path -LiteralPath $outputParent)) {
        New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
    }
    Set-Content -LiteralPath $OutputFile -Value $json -Encoding utf8
}

$json
