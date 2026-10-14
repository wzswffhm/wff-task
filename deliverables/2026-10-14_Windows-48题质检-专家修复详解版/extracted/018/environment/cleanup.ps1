param([Parameter(Mandatory)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop';$full=[IO.Path]::GetFullPath($WorkspaceRoot)
if($full-eq [IO.Path]::GetPathRoot($full)){throw 'Refusing volume root'}
if(Test-Path -LiteralPath $full){Get-ChildItem -LiteralPath $full -Recurse -File -Force|ForEach-Object{[IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal)};Remove-Item -LiteralPath $full -Force -Recurse}
