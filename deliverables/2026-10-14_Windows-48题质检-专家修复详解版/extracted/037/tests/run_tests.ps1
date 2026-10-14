param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop'
$candidate=Join-Path $WorkspaceRoot 'candidate.ps1'
$results=[Collections.Generic.List[object]]::new()
$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot|Out-Null
try {
$fixture=Join-Path $fixtureRoot 'hardlink_split';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'a.txt';$other=Join-Path $fixture 'linked.txt';[IO.File]::WriteAllText($p,'before');New-Item -ItemType HardLink -Path $other -Target $p|Out-Null; & $candidate -Path $p -Text 'after'|Out-Null; ([IO.File]::ReadAllText($p)-eq 'after')-and([IO.File]::ReadAllText($other)-eq 'before') };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='hardlink_split';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'literal_utf8_create';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture '中文 [1].txt';& $candidate -Path $p -Text '更新'|Out-Null;[IO.File]::Exists($p)-and([Convert]::ToHexString([IO.File]::ReadAllBytes($p))-eq 'E69BB4E696B0') };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='literal_utf8_create';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'neighbor_preserved';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'target.txt';$other=Join-Path $fixture 'neighbor.txt';[IO.File]::WriteAllText($other,'safe');& $candidate -Path $p -Text 'new'|Out-Null;[IO.File]::ReadAllText($other)-eq 'safe'  };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='neighbor_preserved';group='P2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'return_and_plain';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture 'plain.txt';[IO.File]::WriteAllText($p,'old');$r=& $candidate -Path $p -Text '';$item=Get-Item -LiteralPath $p;($r.Status-eq 'updated')-and($item.PSIsContainer-eq $false)-and(($item.Attributes-band [IO.FileAttributes]::ReparsePoint)-eq 0)-and([IO.File]::ReadAllBytes($p).Length-eq 0) };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='return_and_plain';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'split_again';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $p=Join-Path $fixture '[源] file.txt';$seed=Join-Path $fixture 'seed.txt';$other=Join-Path $fixture '引用.txt';[IO.File]::WriteAllText($seed,'original');New-Item -ItemType HardLink -Path $other -Target $seed|Out-Null;[IO.File]::Move($seed,$p);$r=& $candidate -Path $p -Text '新';$q=& $candidate -Path $p -Text '再次';(@($r).Count-eq 1)-and($r.Status-eq 'updated')-and($q.Status-eq 'updated')-and([IO.File]::ReadAllText($p)-eq '再次')-and([IO.File]::ReadAllText($other)-eq 'original') };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='split_again';group='F2P';status=$status;detail=$detail})
} finally { if(Test-Path -LiteralPath $fixtureRoot){Remove-Item -LiteralPath $fixtureRoot -Recurse -Force} }
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
$out=@{validity=$validity;score=$score;required=$results.ToArray();testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$results.Count}
$out|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
