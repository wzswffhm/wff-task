param([Parameter(Mandatory)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $WorkspaceRoot){
 $resolved=[IO.Path]::GetFullPath($WorkspaceRoot)
 $marker=Join-Path $resolved '.outside-harbor-pipe-workspace'
 if($resolved-eq [IO.Path]::GetPathRoot($resolved) -or -not(Test-Path -LiteralPath $marker) -or [IO.File]::ReadAllText($marker)-cne 'windows-named-pipe-framing-001'){throw 'Cleanup requires the prepared isolated task workspace'}
 Remove-Item -LiteralPath $resolved -Recurse -Force
}
exit 0
