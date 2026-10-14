param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop'
$candidate=Join-Path $WorkspaceRoot 'candidate.ps1'
$results=[Collections.Generic.List[object]]::new()
$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot|Out-Null
try {
$fixture=Join-Path $fixtureRoot 'enter_release';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $name='Local\Bench_'+[Guid]::NewGuid().ToString('N');$r=& $candidate -Name $name -HoldMs 20 -TimeoutMs 100;$m=[Threading.Mutex]::new($false,$name);try{$ok=$m.WaitOne(100);if($ok){$m.ReleaseMutex()};($r.Status-eq 'entered')-and $ok}finally{$m.Dispose()} };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='enter_release';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'abandoned_enter';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $name='Local\Bench_'+[Guid]::NewGuid().ToString('N');$m=[Threading.Mutex]::new($false,$name);$code='$m=[Threading.Mutex]::new($false,"'+$name+'");$null=$m.WaitOne();[Environment]::Exit(0)';$enc=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code));$p=Start-Process pwsh -ArgumentList @('-NoProfile','-EncodedCommand',$enc) -PassThru -WindowStyle Hidden;if(!$p.WaitForExit(10000)){Stop-Process -Id $p.Id -Force;throw 'Infrastructure: abandoned-mutex child timeout'};if($p.ExitCode-ne 0){throw 'Infrastructure: abandoned-mutex child exit code'};try{$r=& $candidate -Name $name -HoldMs 0 -TimeoutMs 100;$r.Status-eq 'entered'}finally{$m.Dispose()} };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='abandoned_enter';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'other_owner_busy';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $name='Local\Bench_'+[Guid]::NewGuid().ToString('N');$ready=Join-Path $fixture 'ready';$j=Start-ThreadJob -ScriptBlock {param($name,$ready)$m=[Threading.Mutex]::new($false,$name);$null=$m.WaitOne();[IO.File]::WriteAllText($ready,'1');Start-Sleep -Milliseconds 500;$m.ReleaseMutex();$m.Dispose()} -ArgumentList $name,$ready;$readyWatch=[Diagnostics.Stopwatch]::StartNew();while(!(Test-Path -LiteralPath $ready)){if($readyWatch.ElapsedMilliseconds-gt 5000-or $j.State-in @('Failed','Stopped','Completed')){$j|Remove-Job -Force;throw 'Infrastructure: lock-owner readiness sentinel failed'};Start-Sleep -Milliseconds 10};if($j.State-eq 'Failed'){throw 'Infrastructure: lock-owner job failed'};try{$r=& $candidate -Name $name -HoldMs 0 -TimeoutMs 30;$r.Status-eq 'busy'}finally{if($null-eq ($j|Wait-Job -Timeout 10)){$j|Remove-Job -Force;throw 'Infrastructure: lock-owner completion timeout'};if($j.State-eq 'Failed'){$j|Remove-Job -Force;throw 'Infrastructure: lock-owner job exit failure'};$j|Receive-Job -ErrorAction Stop|Out-Null;$j|Remove-Job} };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='other_owner_busy';group='P2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'different_names_hold';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $name='Local\Bench_'+[Guid]::NewGuid().ToString('N');$m=[Threading.Mutex]::new($false,$name);$null=$m.WaitOne();try{$watch=[Diagnostics.Stopwatch]::StartNew();$r=& $candidate -Name ($name+'_other') -HoldMs 100 -TimeoutMs 0;($r.Status-eq 'entered')-and($watch.ElapsedMilliseconds-ge 75)-and($watch.ElapsedMilliseconds-lt 1000)}finally{$m.ReleaseMutex();$m.Dispose()} };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='different_names_hold';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'busy_zero_timeout';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $name='Local\Bench_'+[Guid]::NewGuid().ToString('N');$ready=Join-Path $fixture 'ready';$j=Start-ThreadJob -ScriptBlock {param($name,$ready)$m=[Threading.Mutex]::new($false,$name);$null=$m.WaitOne();[IO.File]::WriteAllText($ready,'1');Start-Sleep -Milliseconds 500;$m.ReleaseMutex();$m.Dispose()} -ArgumentList $name,$ready;$readyWatch=[Diagnostics.Stopwatch]::StartNew();while(!(Test-Path -LiteralPath $ready)){if($readyWatch.ElapsedMilliseconds-gt 5000-or $j.State-in @('Failed','Stopped','Completed')){$j|Remove-Job -Force;throw 'Infrastructure: lock-owner readiness sentinel failed'};Start-Sleep -Milliseconds 10};if($j.State-eq 'Failed'){throw 'Infrastructure: lock-owner job failed'};try{$watch=[Diagnostics.Stopwatch]::StartNew();$r=& $candidate -Name $name -HoldMs 0 -TimeoutMs 0;($r.Status-eq 'busy')-and($watch.ElapsedMilliseconds-lt 400)}finally{if($null-eq ($j|Wait-Job -Timeout 10)){$j|Remove-Job -Force;throw 'Infrastructure: lock-owner completion timeout'};if($j.State-eq 'Failed'){$j|Remove-Job -Force;throw 'Infrastructure: lock-owner job exit failure'};$j|Receive-Job -ErrorAction Stop|Out-Null;$j|Remove-Job} };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='busy_zero_timeout';group='P2P';status=$status;detail=$detail})
} finally { if(Test-Path -LiteralPath $fixtureRoot){Remove-Item -LiteralPath $fixtureRoot -Recurse -Force} }
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
$out=@{validity=$validity;score=$score;required=$results.ToArray();testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$results.Count}
$out|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
