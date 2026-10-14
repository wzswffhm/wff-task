param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop';$candidate=Join-Path $WorkspaceRoot 'candidate.ps1';$results=[Collections.Generic.List[object]]::new();$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
function Clear-Fixtures([string]$Path){if(Test-Path -LiteralPath $Path){Get-ChildItem -LiteralPath $Path -Recurse -File -Force|ForEach-Object{[IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal)};Remove-Item -LiteralPath $Path -Recurse -Force}}
try{New-Item -ItemType Directory -Path $fixtureRoot|Out-Null}catch{throw ('Infrastructure: fixture creation failed: '+$_.Exception.Message)}
try {
$fixture=Join-Path $fixtureRoot 'enable';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture '文件 [1].txt';[IO.File]::WriteAllText($p,'safe');$r=& $candidate -Path $p -Hidden $true -ReadOnly $true;$a=[IO.File]::GetAttributes($p);($r.Status-eq 'updated')-and(($a-band 3)-eq 3) };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='enable';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'clear_preserve_system';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'flag.txt';[IO.File]::WriteAllText($p,'safe');[IO.File]::SetAttributes($p,[IO.FileAttributes]39);$r=& $candidate -Path $p -Hidden $false -ReadOnly $false;$a=[IO.File]::GetAttributes($p);($r.Status-eq 'updated')-and(($a-band 3)-eq 0)-and(($a-band 36)-eq 36) };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='clear_preserve_system';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'mixed_repeat';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'repeat.txt';[IO.File]::WriteAllText($p,'safe');[IO.File]::SetAttributes($p,[IO.FileAttributes]36);& $candidate -Path $p -Hidden $true -ReadOnly $false|Out-Null;& $candidate -Path $p -Hidden $false -ReadOnly $true|Out-Null;$r=& $candidate -Path $p -Hidden $false -ReadOnly $true;$a=[IO.File]::GetAttributes($p);($r.Status-eq 'updated')-and(($a-band 3)-eq 1)-and(($a-band 36)-eq 36) };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='mixed_repeat';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'provider_qualified';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\\OutsideHarborBench\\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'provider.txt';[IO.File]::WriteAllText($p,'safe');$providerPath='FileSystem::'+$p;$r=& $candidate -Path $providerPath -Hidden $true -ReadOnly $false;$a=(Get-Item -LiteralPath $providerPath -Force).Attributes;($r.Status-eq 'updated')-and(($a-band 2)-ne 0)-and(($a-band 1)-eq 0) };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='provider_qualified';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'contents_neighbors';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'target.txt';$q=Join-Path $fixture 'keep.txt';[IO.File]::WriteAllText($p,'target');[IO.File]::WriteAllText($q,'safe');$before=[IO.File]::GetAttributes($q);& $candidate -Path $p -Hidden $false -ReadOnly $false|Out-Null;([IO.File]::ReadAllText($q)-eq 'safe')-and([IO.File]::ReadAllText($p)-eq 'target')-and([IO.File]::GetAttributes($q)-eq $before) };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='contents_neighbors';group='P2P';status=$status;detail=$detail})
} finally {Clear-Fixtures $fixtureRoot}
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
@{validity=$validity;score=$score;testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$results.Count}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
