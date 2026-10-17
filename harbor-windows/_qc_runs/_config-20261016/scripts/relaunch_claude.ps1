param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$TaskPath,

    [Parameter(Mandatory = $true)]
    [string]$JobsDir,

    [Parameter(Mandatory = $true)]
    [string]$JobName,

    [string]$ProfileName = 'claude_opus_5',

    [string]$Model,

    [int]$RelayPort = 18183
)

$ErrorActionPreference = 'Stop'

$profileFile = Join-Path $RepoRoot '.local\harbor-models.psd1'
if (-not (Test-Path -LiteralPath $profileFile -PathType Leaf)) {
    throw "Model profile file missing: $profileFile"
}

$profiles = Import-PowerShellDataFile -LiteralPath $profileFile
$profile = $profiles.Profiles[$ProfileName]
if (-not $profile -or -not $profile.BaseUrl) {
    throw "Profile missing: $ProfileName"
}
if (-not $Model) {
    $Model = [string]$profile.Model
}

$env:PYTHONPATH = $RepoRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$env:WINDOWS_CLAUDE_API_KEY = [string]$profile.ApiKey
$env:WINDOWS_CLAUDE_BASE_URL = "http://host.docker.internal:$RelayPort"
$env:WINDOWS_CLAUDE_MODEL = $Model

Start-Process -FilePath 'harbor.exe' -ArgumentList @(
    'run',
    '-p', $TaskPath,
    '-a', 'agent.windows_claude_code:WindowsClaudeCodeAgent',
    '-m', $Model,
    '--no-force-build',
    '--n-concurrent', '1',
    '--jobs-dir', $JobsDir,
    '--delete',
    '-y',
    '--quiet',
    '--job-name', $JobName
) -WindowStyle Hidden

Write-Output "launched $JobName model=$Model relay_port=$RelayPort"
