if(!$IsWindows-or $PSVersionTable.PSVersion-lt [version]'7.5'){throw 'Native Windows PS7.5 required'}
if((Get-CimInstance Win32_OperatingSystem).Version-ne '10.0.20348'){throw 'Server2022 required'}
