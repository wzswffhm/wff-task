[CmdletBinding()]
param([string]$WorkspaceRoot='C:\workspace',[string]$OutputRoot='C:\logs\verifier')
$ErrorActionPreference='Stop'
[void][IO.Directory]::CreateDirectory($OutputRoot)
$psi=[Diagnostics.ProcessStartInfo]::new((Get-Command pwsh -ErrorAction Stop).Source)
$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
foreach($arg in @('-NoProfile','-NonInteractive','-File',(Join-Path $PSScriptRoot 'run_tests.ps1'),'-WorkspaceRoot',$WorkspaceRoot,'-OutputRoot',$OutputRoot)){$psi.ArgumentList.Add($arg)}
$started=[DateTimeOffset]::UtcNow.ToString('o')
$process=[Diagnostics.Process]::Start($psi)
$stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
if(-not $process.WaitForExit(540000)){$process.Kill($true);$process.WaitForExit();$timedOut=$true}else{$timedOut=$false}
$code=$process.ExitCode;$out=$stdout.GetAwaiter().GetResult();$err=$stderr.GetAwaiter().GetResult();$process.Dispose()
[IO.File]::WriteAllText((Join-Path $OutputRoot 'verifier-stdout.txt'),$out)
[IO.File]::WriteAllText((Join-Path $OutputRoot 'test-stderr.txt'),$err)
$log="VERIFIER BEGIN $started`n$out`nSTDERR`n$err`nVERIFIER END exit=$code timeout=$timedOut $([DateTimeOffset]::UtcNow.ToString('o'))`n"
[IO.File]::WriteAllText((Join-Path $OutputRoot 'verifier-process.log'),$log)
Write-Output $out
if($err){[Console]::Error.WriteLine($err)}
if($timedOut -or $code -ne 0){
    Remove-Item -LiteralPath (Join-Path $OutputRoot 'reward.json') -Force -ErrorAction SilentlyContinue
    @{status='INVALID';score=$null;reason='Verifier execution failed';exit_code=$code;timeout=$timedOut;stderr=$err}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath (Join-Path $OutputRoot 'report.json') -Encoding utf8
    Copy-Item -LiteralPath (Join-Path $OutputRoot 'report.json') -Destination (Join-Path $OutputRoot 'result.json') -Force
    Copy-Item -LiteralPath (Join-Path $OutputRoot 'verifier-process.log') -Destination (Join-Path $OutputRoot 'verifier.log') -Force
    Remove-Item -LiteralPath (Join-Path $OutputRoot 'reward.txt') -Force -ErrorAction SilentlyContinue
    exit 1
}
# Emit the standard verifier representations from this actual execution.
Copy-Item -LiteralPath (Join-Path $OutputRoot 'report.json') -Destination (Join-Path $OutputRoot 'result.json') -Force
Copy-Item -LiteralPath (Join-Path $OutputRoot 'verifier-process.log') -Destination (Join-Path $OutputRoot 'verifier.log') -Force
$actual=Get-Content -LiteralPath (Join-Path $OutputRoot 'report.json') -Raw -Encoding utf8|ConvertFrom-Json
if($actual.status -ne 'VALID' -or $actual.score -notin @(0,1)){throw 'Invalid actual result cannot emit a reward'}
[IO.File]::WriteAllText((Join-Path $OutputRoot 'reward.txt'),([string]$actual.score+"`n"))
exit 0
