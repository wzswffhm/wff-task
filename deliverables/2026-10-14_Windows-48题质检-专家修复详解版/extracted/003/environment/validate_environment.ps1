$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Version.Build -ne 20348) { throw 'Windows Server 2022 build 20348 required' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'x64 Windows required' }
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework compiler missing' }
exit 0
