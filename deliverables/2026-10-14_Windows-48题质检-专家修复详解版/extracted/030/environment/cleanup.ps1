param([Parameter(Mandatory)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop';$full=[IO.Path]::GetFullPath($WorkspaceRoot)
if($full-eq [IO.Path]::GetPathRoot($full)-or $full-eq [IO.Path]::GetFullPath($PSScriptRoot)){throw 'Unsafe cleanup root'}
if(Test-Path -LiteralPath $full){Remove-Item -LiteralPath $full -Force -Recurse}
exit 0
