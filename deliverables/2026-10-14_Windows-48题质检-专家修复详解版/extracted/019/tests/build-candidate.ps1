param([Parameter(Mandatory=$true)][string]$Workspace, [Parameter(Mandatory=$true)][string]$Log)
$ErrorActionPreference = 'Stop'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $csc)) { throw 'Required compiler is missing' }
$bin = Join-Path $Workspace 'bin'
if (Test-Path -LiteralPath $bin) { Get-ChildItem -LiteralPath $bin -Force | Remove-Item -Recurse -Force }
else { New-Item -ItemType Directory -Path $bin | Out-Null }
$src = Join-Path $Workspace 'src'
if (-not (Test-Path -LiteralPath $src)) {
    [IO.File]::WriteAllText($Log, 'Candidate has no src directory')
    return 1
}
$entries = @(Get-ChildItem -LiteralPath $src -Recurse -Force)
if (@($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
    [IO.File]::WriteAllText($Log, 'Candidate contains disallowed reparse source entries')
    return 1
}
$sources = @($entries | Where-Object { -not $_.PSIsContainer -and $_.Extension -ieq '.cs' } | Sort-Object FullName)
if ($sources.Count -eq 0) {
    [IO.File]::WriteAllText($Log, 'Candidate has no C# source files')
    return 1
}
$response = Join-Path (Split-Path $Log) 'candidate-build.rsp'
$options = @('/nologo', '/codepage:65001', '/langversion:5', '/target:exe', '/platform:x64', '/optimize+', '/r:System.Web.Extensions.dll', ('/out:"' + (Join-Path $bin 'WinPublish.exe') + '"'))
$options += @($sources | ForEach-Object { '"' + $_.FullName + '"' })
[IO.File]::WriteAllLines($response, $options, [Text.UTF8Encoding]::new($true))
& $csc ('@' + $response) *> $Log
$code = $LASTEXITCODE
if ($code -eq 0 -and -not (Test-Path (Join-Path $bin 'WinPublish.exe'))) { throw 'Compiler reported success without a fresh executable' }
return [int]$code
