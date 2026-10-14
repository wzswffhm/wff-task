$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.ToString() -ne '7.4.18'){throw 'PowerShell version mismatch'}
if([Environment]::OSVersion.Version.Build -ne 20348){throw 'Windows build mismatch'}
$sub='Software\RegistryPatchEnvProbe\'+[Guid]::NewGuid().ToString('N')
$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($sub);$k.Close();[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($sub)
exit 0
