$ErrorActionPreference='Stop'
[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree('Software\RegistryPatchBench',$false)
[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree('Software\RegistryPatchSmoke',$false)
foreach($p in 'C:\logs\verifier\fixtures','C:\logs\verifier\cases.json','C:\logs\verifier\report.json','C:\logs\verifier\reward.json','C:\logs\verifier\reward.txt'){if(Test-Path -LiteralPath $p){Remove-Item -LiteralPath $p -Recurse -Force}}
exit 0
