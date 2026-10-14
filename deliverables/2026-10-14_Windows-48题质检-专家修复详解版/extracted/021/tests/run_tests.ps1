param([string]$WorkspaceRoot,[string]$OutputPath)
$ErrorActionPreference='Stop';$results=[Collections.Generic.List[object]]::new()
$keep=Join-Path $WorkspaceRoot 'unrelated-keep.txt';[IO.File]::WriteAllText($keep,'unchanged')
$auditRoot=Join-Path (Split-Path -Parent $OutputPath) ('pipe-audit-'+[guid]::NewGuid());$null=New-Item -ItemType Directory -Path $auditRoot
function Spawn($script,$arg){$si=[Diagnostics.ProcessStartInfo]::new();$si.FileName=(Get-Process -Id $PID).Path;$si.UseShellExecute=$false;$si.CreateNoWindow=$true;$si.RedirectStandardOutput=$true;$si.RedirectStandardError=$true;foreach($v in @('-NoProfile','-File',$script,$arg)){$si.ArgumentList.Add($v)};$p=[Diagnostics.Process]::Start($si);[pscustomobject]@{p=$p;o=$p.StandardOutput.ReadToEndAsync();e=$p.StandardError.ReadToEndAsync()}}
function Case($id,$group,[string[]]$messages,$mode,$expected,[string[]]$acks){
 $dir=Join-Path $auditRoot $id;$null=New-Item -ItemType Directory -Path $dir
 $c=@{pipe='oh-'+[guid]::NewGuid();messages=$messages;mode=$mode;ready=(Join-Path $dir 'ready');server_result=(Join-Path $dir 'server.json');client_result=(Join-Path $dir 'client.json');candidate=(Join-Path $WorkspaceRoot 'candidate.ps1');timeout=1800};if($mode-eq'normal'){$c.timeout=10000};$cp=Join-Path $dir 'case.json';$c|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $cp
 $s=$null;$p=$null;$status='FAIL';$detail=''
 try{
 if($mode-ne'missing'){$s=Spawn (Join-Path $PSScriptRoot 'server.ps1') $cp;$clock=[Diagnostics.Stopwatch]::StartNew();while(-not(Test-Path $c.ready)-and-not$s.p.HasExited-and$clock.ElapsedMilliseconds-lt20000){Start-Sleep -Milliseconds 15};if(-not(Test-Path $c.ready)){throw 'Infrastructure: server startup'}}
 $p=Spawn (Join-Path $PSScriptRoot 'invoke_candidate.ps1') $cp;if(-not$p.p.WaitForExit(22000)){throw 'Candidate deadline'}
 $p.o.Result|Set-Content (Join-Path $dir 'stdout');$p.e.Result|Set-Content (Join-Path $dir 'stderr')
 $r=Get-Content $c.client_result -Raw|ConvertFrom-Json;if($r.error){throw $r.error};if(@($r.records).Count-ne1){throw 'Output count'};$v=@($r.records)[0]
 if($v.Status-cne$expected-or$null-eq$v.Acks-or@($v.Acks).Count-ne$acks.Count){throw 'Result mismatch'};for($i=0;$i-lt$acks.Count;$i++){if($v.Acks[$i]-cne$acks[$i]){throw 'Payload mismatch'}}
 if($r.elapsed_ms-gt($c.timeout+3000)){throw 'Deadline exceeded'}
 if($s){if(-not$s.p.WaitForExit(4000)){throw 'Connection not closed'};$a=Get-Content $c.server_result -Raw|ConvertFrom-Json;if(-not$a.constructed-or-not$a.message_mode-or-not$a.connected){throw 'Server health proof missing'};if($expected-eq'completed'-and(-not$a.done_sent-or-not$a.complete_received-or$a.error)){throw 'Completion sentinel missing'}}
 if([IO.File]::ReadAllText($keep)-cne 'unchanged'){throw 'Unrelated file changed'}
 $status='PASS'
 }catch{$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}finally{foreach($j in @($p,$s)){if($j){if(-not$j.p.HasExited){$j.p.Kill($true);$j.p.WaitForExit()};$j.p.Dispose()}}}
 $results.Add(@{id=$id;group=$group;status=$status;detail=$detail})
}
Case 'small_ascii' 'P2P' @('"hi"','42') 'normal' 'completed' @('"hi"','42')
Case 'empty_handshake' 'P2P' @() 'normal' 'completed' @()
Case 'no_server_timeout' 'P2P' @('"hi"') 'missing' 'timeout' @()
Case 'ready_deadline' 'P2P' @('"hi"') 'stall_ready' 'timeout' @()
$long='{"body":"'+('x'*12000)+'"}';Case 'long_message' 'F2P' @($long) 'normal' 'completed' @($long)
$unicode='{"text":"中文🙂"}';Case 'unicode_roundtrip' 'F2P' @($unicode) 'normal' 'completed' @($unicode)
$mixed=@('""',"{`n`"x`":1`n}",$unicode,$long,'null');Case 'multiple_message_boundaries' 'F2P' $mixed 'normal' 'completed' $mixed
Case 'done_required' 'P2P' @('"hi"') 'stall_done' 'timeout' @('"hi"')
Case 'ack_deadline_preserves_prefix' 'P2P' @('"first"','"second"') 'stall_ack' 'timeout' @('"first"')
Case 'peer_close_preserves_prefix' 'P2P' @('"first"','"second"') 'disconnect' 'timeout' @('"first"')
Remove-Item -LiteralPath $keep -Force
$manifest=Get-Content (Join-Path $PSScriptRoot 'rubric.json') -Raw|ConvertFrom-Json
$valid=$results.Count-eq$manifest.required.Count
foreach($req in $manifest.required){$matches=@($results|Where-Object{$_.id-ceq$req.id-and$_.group-ceq$req.group});if($matches.Count-ne1-or$matches[0].status-notin@('PASS','FAIL')){$valid=$false}}
$invalid=-not$valid;$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq0)}
@{validity=$(if($invalid){'INVALID'}else{'VALID'});score=$score;testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$manifest.required.Count;required=$manifest.required;artifact_directory=$auditRoot}|ConvertTo-Json -Depth 8|Set-Content $OutputPath
if($invalid){exit 2}elseif($score-eq1){exit 0}else{exit 1}
