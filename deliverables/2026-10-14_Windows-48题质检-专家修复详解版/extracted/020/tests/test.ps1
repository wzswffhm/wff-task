param([string]$WorkspaceRoot='C:\workspace',[string]$OutputPath='C:\logs\verifier\reward.json')
$ErrorActionPreference='Stop'
$detailPath='C:\logs\verifier\results.json'
& (Join-Path $PSScriptRoot 'run_tests.ps1') -WorkspaceRoot $WorkspaceRoot -OutputPath $detailPath
$code=$LASTEXITCODE
if(Test-Path -LiteralPath $detailPath){
  $result=Get-Content -LiteralPath $detailPath -Raw | ConvertFrom-Json
  $rewardJson=@{reward=[int]$result.score} | ConvertTo-Json -Compress
  [IO.File]::WriteAllText($OutputPath,$rewardJson,[Text.UTF8Encoding]::new($false))
}
exit $code
