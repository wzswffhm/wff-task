[CmdletBinding()]
param(
    [switch]$EnvironmentOnly
)

$ErrorActionPreference = 'Stop'
$probeRoot = Join-Path $env:TEMP ('windows-powershell-ads-docker-' + [guid]::NewGuid().ToString('N'))

try {
    if ($env:OS -ne 'Windows_NT') { throw 'The container is not Windows.' }
    if (-not (Test-Path -LiteralPath 'C:\workspace\src\ZoneMarkCleaner.ps1' -PathType Leaf)) {
        throw 'The workspace source file is missing from the image.'
    }

    New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null
    $probe = Join-Path $probeRoot 'probe.txt'
    [System.IO.File]::WriteAllText($probe, 'docker-smoke')
    Set-Content -LiteralPath $probe -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
    $before = (Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash

    if ($EnvironmentOnly) {
        Remove-Item -LiteralPath $probe -Stream 'Zone.Identifier' -Force -ErrorAction Stop
        $result = [pscustomobject]@{ Status = 'EnvironmentOnly' }
    }
    else {
        . 'C:\workspace\src\ZoneMarkCleaner.ps1'
        $result = @(Clear-ZoneIdentifier -Path $probe)
    }

    $remaining = @(Get-Item -LiteralPath $probe -Stream * -Force | Where-Object { $_.Stream -ieq 'Zone.Identifier' })
    $after = (Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash
    if (-not $EnvironmentOnly -and ($result.Count -ne 1 -or $result[0].Status -ne 'Removed')) {
        throw 'The cleaner did not report Removed.'
    }
    if ($remaining.Count -ne 0) { throw 'Zone.Identifier remains after cleanup.' }
    if ($before -ne $after) { throw 'The primary file content changed.' }

    [pscustomobject]@{
        status = 'DOCKER_SMOKE_OK'
        os = [Environment]::OSVersion.VersionString
        powershell = $PSVersionTable.PSVersion.ToString()
        result = if ($EnvironmentOnly) { $result } else { $result[0] }
    } | ConvertTo-Json -Depth 5 -Compress
}
finally {
    if (Test-Path -LiteralPath $probeRoot) {
        Remove-Item -LiteralPath $probeRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
