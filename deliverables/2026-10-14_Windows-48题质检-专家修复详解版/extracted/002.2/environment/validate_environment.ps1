param([Parameter(Mandatory=$true)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
if (-not [Environment]::Is64BitOperatingSystem) {throw '64-bit Windows required'}
$csc=Join-Path $env:SystemRoot 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $csc)) {throw 'Framework compiler missing'}
$drive=New-Object IO.DriveInfo([IO.Path]::GetPathRoot($WorkspaceRoot))
if ($drive.DriveFormat -ne 'NTFS') {throw 'NTFS required'}
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {throw 'Elevated Windows token required'}
$fixture=Join-Path $WorkspaceRoot 'state\cases\CASE-2231'
if (@([IO.Directory]::GetFiles(('\\?\'+$fixture),'*','AllDirectories')).Count -ne 16) {throw 'Incomplete field fixture'}
Write-Host 'Windows/NTFS/x86 compiler/admin readiness passed'
