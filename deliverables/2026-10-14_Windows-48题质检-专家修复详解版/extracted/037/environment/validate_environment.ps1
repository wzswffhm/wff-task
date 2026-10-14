$ErrorActionPreference='Stop'
if(!$IsWindows){throw 'Windows required'}
if($PSVersionTable.PSVersion -lt [version]'7.5'){throw 'PowerShell 7.5 required'}
$os=Get-CimInstance Win32_OperatingSystem
if($os.Version-ne '10.0.20348'){throw 'Windows Server 2022 build 20348 required'}
