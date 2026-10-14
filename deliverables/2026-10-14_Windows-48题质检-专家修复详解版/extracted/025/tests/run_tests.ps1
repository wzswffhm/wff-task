param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop';$candidate=Join-Path $WorkspaceRoot 'candidate.ps1';$results=[Collections.Generic.List[object]]::new();$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
function Clear-Fixtures([string]$Path){if(Test-Path -LiteralPath $Path){Get-ChildItem -LiteralPath $Path -Recurse -File -Force|ForEach-Object{[IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal)};Remove-Item -LiteralPath $Path -Recurse -Force}}
try{New-Item -ItemType Directory -Path $fixtureRoot|Out-Null}catch{throw ('Infrastructure: fixture creation failed: '+$_.Exception.Message)}
try {
$fixture=Join-Path $fixtureRoot 'native_default_unicode';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $r=& $candidate -SubKey $reg -Action Set -Value '默认值';$g=& $candidate -SubKey $reg -Action Get;$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{($r.Status-eq 'set')-and($g.Status-eq 'found')-and($g.Value-eq '默认值')-and($k.GetValue('')-eq '默认值')-and($k.GetValueNames()-contains '')}finally{if($k){$k.Dispose()}} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='native_default_unicode';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'empty_replace';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { & $candidate -SubKey $reg -Action Set -Value 'old'|Out-Null;& $candidate -SubKey $reg -Action Set -Value ''|Out-Null;$g=& $candidate -SubKey $reg -Action Get;$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{($g.Status-eq 'found')-and($g.Value-eq '')-and($k.GetValueNames()-contains '')-and($k.GetValue('')-eq '')}finally{if($k){$k.Dispose()}} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='empty_replace';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'remove_existing';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($reg);$k.SetValue('','old');$k.Dispose();$r=& $candidate -SubKey $reg -Action Remove;$g=& $candidate -SubKey $reg -Action Get;$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{($r.Status-in @('removed','missing'))-and($g.Status-eq 'missing')-and(!$k-or $k.GetValueNames()-notcontains '')}finally{if($k){$k.Dispose()}} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='remove_existing';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'named_values_subkeys';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($reg);$k.SetValue('Keep',[string[]]@('a','b'),[Microsoft.Win32.RegistryValueKind]::MultiString);$c=$k.CreateSubKey('child');$c.SetValue('A','B');$c.Dispose();$k.Dispose();& $candidate -SubKey $reg -Action Set -Value x|Out-Null;& $candidate -SubKey $reg -Action Remove|Out-Null;$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);$c=$k.OpenSubKey('child');try{($k.GetValueKind('Keep')-eq 'MultiString')-and(($k.GetValue('Keep')-join '|')-eq 'a|b')-and($c.GetValue('A')-eq 'B')}finally{$c.Dispose();$k.Dispose()} };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='named_values_subkeys';group='P2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'missing_repeat';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $r=& $candidate -SubKey $reg -Action Remove;$r2=& $candidate -SubKey $reg -Action Remove;$g=& $candidate -SubKey $reg -Action Get;($r.Status-in @('missing','removed'))-and($r2.Status-in @('missing','removed'))-and($g.Status-eq 'missing') };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='missing_repeat';group='P2P';status=$status;detail=$detail})
} finally {Clear-Fixtures $fixtureRoot}
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
@{validity=$validity;score=$score;testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$results.Count}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
