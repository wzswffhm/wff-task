[CmdletBinding()]
param(
    [string]$TaskRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$probeRoot = Join-Path $env:TEMP ('windows-powershell-ads-probe-' + [guid]::NewGuid().ToString('N'))
$probeFile = Join-Path $probeRoot 'probe.txt'

try {
    if ($env:OS -ne 'Windows_NT') {
        throw 'This pilot requires Windows.'
    }

    New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null
    Set-Content -LiteralPath $probeFile -Value 'probe' -Encoding UTF8
    Set-Content -LiteralPath $probeFile -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
    $stream = Get-Item -LiteralPath $probeFile -Stream 'Zone.Identifier' -ErrorAction SilentlyContinue
    if ($null -eq $stream) {
        throw 'NTFS alternate data streams are unavailable.'
    }

    Write-Output ('PowerShell: ' + $PSVersionTable.PSVersion.ToString())
    Write-Output ('Workspace: ' + (Resolve-Path -LiteralPath (Join-Path $TaskRoot 'workspace')).Path)
    Write-Output 'OK'
}
catch {
    Write-Error $_.Exception.Message
    exit 2
}
finally {
    if (Test-Path -LiteralPath $probeRoot) {
        Remove-Item -LiteralPath $probeRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
