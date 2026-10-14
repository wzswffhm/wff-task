param([Parameter(Mandatory)][string]$WorkspaceRoot)
$full=[IO.Path]::GetFullPath($WorkspaceRoot)
if($full-eq [IO.Path]::GetPathRoot($full)){throw 'Refusing volume root'}
if(Test-Path -LiteralPath $full){Remove-Item -LiteralPath $full -Force -Recurse}
