param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop'
$candidate=Join-Path $WorkspaceRoot 'candidate.ps1'
$results=[Collections.Generic.List[object]]::new()
$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot|Out-Null
try {
$fixture=Join-Path $fixtureRoot 'recursive_literal';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $root=Join-Path $fixture 'root';New-Item -ItemType Directory -Path (Join-Path $root '子目录') -Force|Out-Null;[IO.File]::WriteAllText((Join-Path $root '[a].LOG'),'a');[IO.File]::WriteAllText((Join-Path $root '子目录\b.log'),'b');$r=& $candidate -Root $root;(@($r.Files)-join '|')-eq '[a].LOG|子目录\b.log'  };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='recursive_literal';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'junction_skipped';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $root=Join-Path $fixture 'root';$outside=Join-Path $fixture 'outside';New-Item -ItemType Directory -Path $root,$outside -Force|Out-Null;[IO.File]::WriteAllText((Join-Path $root 'real.log'),'r');[IO.File]::WriteAllText((Join-Path $outside 'secret.log'),'s');New-Item -ItemType Junction -Path (Join-Path $root 'external') -Target $outside|Out-Null;New-Item -ItemType Junction -Path (Join-Path $root 'loop') -Target $root|Out-Null;$r=& $candidate -Root $root;(@($r.Files)-join '|')-eq 'real.log'  };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='junction_skipped';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'empty_no_mutation';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $root=Join-Path $fixture 'empty';New-Item -ItemType Directory -Path $root|Out-Null;[IO.File]::WriteAllText((Join-Path $root 'keep.txt'),'safe');$r=& $candidate -Root $root;(@($r.Files).Count-eq 0)-and([IO.File]::ReadAllText((Join-Path $root 'keep.txt'))-eq 'safe') };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='empty_no_mutation';group='P2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'internal_link_sort_preserve';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $root=Join-Path $fixture 'root';$inner=Join-Path $root 'inner';New-Item -ItemType Directory -Path $inner -Force|Out-Null;[IO.File]::WriteAllText((Join-Path $root 'z.log'),'z');[IO.File]::WriteAllText((Join-Path $root 'A.LOG'),'a');[IO.File]::WriteAllText((Join-Path $inner 'c.LoG'),'c');[IO.File]::WriteAllText((Join-Path $root 'ignore.log.txt'),'n');New-Item -ItemType Junction -Path (Join-Path $root 'alias') -Target $inner|Out-Null;$r=& $candidate -Root $root;(@($r.Files)-join '|')-eq 'A.LOG|inner\c.LoG|z.log' -and [IO.File]::ReadAllText((Join-Path $root 'z.log'))-eq 'z' -and [IO.File]::ReadAllText((Join-Path $root 'A.LOG'))-eq 'a' -and [IO.File]::ReadAllText((Join-Path $inner 'c.LoG'))-eq 'c'  };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='internal_link_sort_preserve';group='F2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'empty_array_shape';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $root=Join-Path $fixture 'nothing';New-Item -ItemType Directory -Path $root|Out-Null;$r=& $candidate -Root $root;(@($r).Count-eq 1)-and($null-ne $r.Files)-and(@($r.Files).Count-eq 0) };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='empty_array_shape';group='P2P';status=$status;detail=$detail})
$fixture=Join-Path $fixtureRoot 'symbolic_links_skipped';New-Item -ItemType Directory -Path $fixture|Out-Null
$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')
$status='FAIL';$detail=''
try {$passed=& { $root=Join-Path $fixture 'root';$outside=Join-Path $fixture 'outside';New-Item -ItemType Directory -Path $root,$outside|Out-Null;$secret=Join-Path $outside 'secret.log';[IO.File]::WriteAllText($secret,'safe');[IO.File]::WriteAllText((Join-Path $root 'real.log'),'real');New-Item -ItemType SymbolicLink -Path (Join-Path $root 'dirlink') -Target $outside|Out-Null;New-Item -ItemType SymbolicLink -Path (Join-Path $root 'filelink.log') -Target $secret|Out-Null;$r=& $candidate -Root $root;(@($r.Files)-join '|')-eq 'real.log' -and [IO.File]::ReadAllText($secret)-eq 'safe'  };if($passed-eq $true){$status='PASS'}}catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}
$results.Add(@{id='symbolic_links_skipped';group='F2P';status=$status;detail=$detail})
} finally { if(Test-Path -LiteralPath $fixtureRoot){Remove-Item -LiteralPath $fixtureRoot -Recurse -Force} }
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
$out=@{validity=$validity;score=$score;required=$results.ToArray();testcases=$results.ToArray();testcase_pass_count=@($results|Where-Object status -eq 'PASS').Count;testcase_total=$results.Count}
$out|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
