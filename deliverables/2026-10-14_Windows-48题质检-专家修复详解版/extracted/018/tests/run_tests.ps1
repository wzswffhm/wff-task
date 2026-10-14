param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop';$candidate=Join-Path $WorkspaceRoot 'candidate.ps1';$results=[Collections.Generic.List[object]]::new();$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
function Clear-Fixtures([string]$Path){if(Test-Path -LiteralPath $Path){Get-ChildItem -LiteralPath $Path -Recurse -File -Force|ForEach-Object{[IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal)};Remove-Item -LiteralPath $Path -Recurse -Force}}
try{New-Item -ItemType Directory -Path $fixtureRoot|Out-Null}catch{throw ('Infrastructure: fixture creation failed: '+$_.Exception.Message)}
try {
$fixture=Join-Path $fixtureRoot 'native_signal';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $n='Local\Bench_'+[Guid]::NewGuid().ToString('N');$e=[Threading.EventWaitHandle]::new($false,'ManualReset',$n);try{$r=& $candidate -Name $n -Action Signal -TimeoutMs 0;($r.Status-eq 'signaled')-and($e.WaitOne(0))}finally{$e.Dispose()} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='native_signal';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'native_wait_persist';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $n='Local\Bench_'+[Guid]::NewGuid().ToString('N');$e=[Threading.EventWaitHandle]::new($true,'ManualReset',$n);try{$r=& $candidate -Name $n -Action Wait -TimeoutMs 0;$r2=& $candidate -Name $n -Action Wait -TimeoutMs 0;($r.Status-eq 'signaled')-and($r2.Status-eq 'signaled')-and($e.WaitOne(0))}finally{$e.Dispose()} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='native_wait_persist';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'cross_process_signal';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $n='Local\Bench_'+[Guid]::NewGuid().ToString('N');$e=[Threading.EventWaitHandle]::new($false,'ManualReset',$n);try{$child=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList @('-NoProfile','-File',('"'+$candidate+'"'),'-Name',$n,'-Action','Signal','-TimeoutMs','0') -PassThru -WindowStyle Hidden;try{if(!$child.WaitForExit(15000)){throw 'Infrastructure: event child completion timeout'};$e.WaitOne(0)-and($child.ExitCode-eq 0)}finally{if(!$child.HasExited){$child.Kill($true);$child.WaitForExit(5000)|Out-Null};$child.Dispose()}}finally{$e.Dispose()} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='cross_process_signal';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'timeout';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $n='Local\Bench_'+[Guid]::NewGuid().ToString('N');$r=& $candidate -Name $n -Action Wait -TimeoutMs 30;$r.Status-eq 'timeout'  };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='timeout';group='P2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'other_name_unchanged';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $n='Local\Bench_'+[Guid]::NewGuid().ToString('N');$e=[Threading.EventWaitHandle]::new($true,'ManualReset',$n);try{$r=& $candidate -Name ($n+'_other') -Action Wait -TimeoutMs 0;($r.Status-eq 'timeout')-and($e.WaitOne(0))}finally{$e.Dispose()} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='other_name_unchanged';group='P2P';status=$status;detail=$detail})
} finally {Clear-Fixtures $fixtureRoot}
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
@{validity=$validity;score=$score;testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$results.Count}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
