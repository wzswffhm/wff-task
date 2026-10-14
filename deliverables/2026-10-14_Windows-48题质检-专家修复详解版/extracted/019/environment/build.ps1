param()
$ErrorActionPreference = 'Stop'
$root = 'C:\testbed'
$bin = Join-Path $root 'bin'
if (Test-Path $bin) {
    Get-ChildItem -LiteralPath $bin -Force | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $bin | Out-Null
}
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { throw 'Required .NET Framework x64 C# compiler missing' }
$sources = @(Get-ChildItem (Join-Path $root 'src') -Filter '*.cs' -Recurse | ForEach-Object { $_.FullName })
if ($sources.Count -eq 0) { throw 'No C# source files' }
& $csc /nologo /codepage:65001 /langversion:5 /target:exe /platform:x64 /optimize+ /r:System.Web.Extensions.dll (('/out:' + (Join-Path $bin 'WinPublish.exe'))) $sources
if ($LASTEXITCODE -ne 0) { throw ('Build failed: ' + $LASTEXITCODE) }
