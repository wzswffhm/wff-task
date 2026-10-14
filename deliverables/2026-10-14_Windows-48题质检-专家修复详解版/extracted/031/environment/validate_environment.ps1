$ErrorActionPreference='Stop'
if(!$IsWindows-or $PSVersionTable.PSVersion.ToString()-ne '7.5.10'){throw 'Frozen Windows PowerShell runtime required'}
if((Get-CimInstance Win32_OperatingSystem).Version-ne '10.0.20348'){throw 'Frozen Windows build required'}
