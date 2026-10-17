param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$ProfileName,

    [int]$Port = 18183
)

$ErrorActionPreference = 'Stop'

$profileFile = Join-Path $RepoRoot '.local\harbor-models.psd1'
$relayScript = Join-Path $PSScriptRoot 'host_api_relay.py'

if (-not (Test-Path -LiteralPath $profileFile -PathType Leaf)) {
    throw "Model profile file missing: $profileFile"
}
if (-not (Test-Path -LiteralPath $relayScript -PathType Leaf)) {
    throw "Relay script missing: $relayScript"
}

$profiles = Import-PowerShellDataFile -LiteralPath $profileFile
$profile = $profiles.Profiles[$ProfileName]
if (-not $profile -or -not $profile.BaseUrl) {
    throw "Profile missing: $ProfileName"
}

$env:RELAY_UPSTREAM_URL = [string]$profile.BaseUrl
$env:RELAY_PORT = [string]$Port

$env:THINKING_ENABLED = 'true'
$env:THINKING_MODE = 'adaptive'
$env:THINKING_BUDGET_TOKENS = '24000'
$env:MAX_TOKENS_LIMIT = '65535'

$env:MODEL_TEMPERATURE = '1'
$env:MODEL_TOP_P = '0.95'
$env:MODEL_TOP_K = '20'
$env:ENABLE_THINKING = 'true'
$env:REASONING_EFFORT = 'xhigh'
$env:MID_SYSTEM_MESSAGE_STRATEGY = 'merge'

$python = (Get-Command python -ErrorAction Stop).Source
Start-Process -FilePath $python -ArgumentList @($relayScript) -WindowStyle Hidden

Write-Output "started relay profile=$ProfileName port=$Port"
