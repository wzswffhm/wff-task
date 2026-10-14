$ErrorActionPreference='Stop'
if(-not $IsWindows-or(Get-CimInstance Win32_OperatingSystem).BuildNumber-ne '20348'){throw 'Windows build20348 required'}
if($PSVersionTable.PSVersion.ToString()-ne '7.5.10'){throw 'PowerShell7.5.10 required'}
exit 0
