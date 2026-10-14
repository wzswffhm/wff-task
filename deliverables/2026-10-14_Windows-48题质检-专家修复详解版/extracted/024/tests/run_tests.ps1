param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop';$candidate=Join-Path $WorkspaceRoot 'candidate.ps1';$results=[Collections.Generic.List[object]]::new();$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
function Clear-Fixtures([string]$Path){if(Test-Path -LiteralPath $Path){Get-ChildItem -LiteralPath $Path -Recurse -File -Force|ForEach-Object{[IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal)};Remove-Item -LiteralPath $Path -Recurse -Force}}
try{New-Item -ItemType Directory -Path $fixtureRoot|Out-Null}catch{throw ('Infrastructure: fixture creation failed: '+$_.Exception.Message)}
try {
$fixture=Join-Path $fixtureRoot 'real_stream_utf8';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture '文档 [1].txt';[IO.File]::WriteAllText($p,'main');$r=& $candidate -Path $p -Stream meta -Action Set -Value '秘密';$g=& $candidate -Path $p -Stream meta -Action Get;$streams=Get-Item -LiteralPath $p -Stream *;($r.Status-eq 'set')-and($g.Status-eq 'found')-and($g.Value-eq '秘密')-and(@($streams|Where-Object Stream -eq 'meta').Count-eq 1)-and([Convert]::ToHexString([IO.File]::ReadAllBytes($p+':meta'))-eq 'E7A798E5AF86') };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='real_stream_utf8';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'replace_empty';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'replace.txt';[IO.File]::WriteAllText($p,'main');& $candidate -Path $p -Stream data -Action Set -Value 'long text'|Out-Null;& $candidate -Path $p -Stream data -Action Set -Value ''|Out-Null;$g=& $candidate -Path $p -Stream data -Action Get;($g.Status-eq 'found')-and($g.Value-eq '')-and([IO.File]::ReadAllBytes($p+':data').Length-eq 0) };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='replace_empty';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'remove_existing';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'remove.txt';[IO.File]::WriteAllText($p,'main');[IO.File]::WriteAllText($p+':data','old');$r=& $candidate -Path $p -Stream data -Action Remove;$g=& $candidate -Path $p -Stream data -Action Get;$streams=Get-Item -LiteralPath $p -Stream *;($r.Status-eq 'removed')-and($g.Status-eq 'missing')-and(@($streams|Where-Object Stream -eq 'data').Count-eq 0) };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='remove_existing';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'main_other_preserved';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'preserve.txt';[IO.File]::WriteAllText($p,'main');[IO.File]::WriteAllText($p+':other','safe');& $candidate -Path $p -Stream target -Action Set -Value x|Out-Null;& $candidate -Path $p -Stream target -Action Remove|Out-Null;([IO.File]::ReadAllText($p)-eq 'main')-and([IO.File]::ReadAllText($p+':other')-eq 'safe') };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='main_other_preserved';group='P2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'missing_idempotent';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'missing.txt';[IO.File]::WriteAllText($p,'safe');$r=& $candidate -Path $p -Stream none -Action Remove;$r2=& $candidate -Path $p -Stream none -Action Remove;$g=& $candidate -Path $p -Stream none -Action Get;($r.Status-eq 'missing')-and($r2.Status-eq 'missing')-and($g.Status-eq 'missing')-and([IO.File]::ReadAllText($p)-eq 'safe') };if(@($passed).Count-eq 1-and $passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='missing_idempotent';group='P2P';status=$status;detail=$detail})
} finally {Clear-Fixtures $fixtureRoot}
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
@{validity=$validity;score=$score;testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$results.Count}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
