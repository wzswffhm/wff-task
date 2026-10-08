[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutPath,
    [ValidateRange(3, 100)][int]$Attempts = 3,
    [string]$Environment,
    [switch]$ForceBuild
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$arguments = @(
    (Join-Path $scriptRoot 'run_qc.py'),
    '--input', $InputPath,
    '--out', $OutPath,
    '--attempts', $Attempts
)
if ($Environment) { $arguments += @('--environment', $Environment) }
if ($ForceBuild) { $arguments += '--force-build' }
& python @arguments
exit $LASTEXITCODE

