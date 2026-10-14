$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.ToString() -ne '7.6.5') { throw 'PowerShell 7.6.5 is required' }
if ($env:OS -ne 'Windows_NT' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Windows amd64 is required' }
$python = if (Test-Path 'C:\Python\python.exe') { 'C:\Python\python.exe' } else { (Get-Command python -ErrorAction Stop).Source }
& $python -I -c 'import os,sys,struct,subprocess; assert os.name=="nt" and sys.version_info[:3]==(3,12,14) and struct.calcsize("P")==8; p=subprocess.run([sys.executable,"-I","-c","print(123)"],capture_output=True,timeout=5); assert p.returncode==0 and p.stdout.strip()==b"123"; print(sys.version)'
if ($LASTEXITCODE -ne 0) { throw 'Python/child health preflight failed' }
