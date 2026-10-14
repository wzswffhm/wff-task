param([object[]]$Cases,[string]$OutputRoot,[long]$StartedAt)
$ErrorActionPreference='Stop'
$manifest=Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'required_testcases.json')|ConvertFrom-Json
$ids=@($manifest|ForEach-Object id);$present=@($Cases|ForEach-Object id)
$groups=@{};foreach($item in $manifest){$groups[$item.id]=$item.group}
$invalid=$Cases.Count -ne $ids.Count -or @($present|Select-Object -Unique).Count -ne $ids.Count -or @(Compare-Object $ids $present).Count -gt 0 -or @($Cases|Where-Object {$_.status -notin 'PASS','FAIL' -or $_.group -ne $groups[$_.id]}).Count -gt 0
$fail=@($Cases|Where-Object {$_.status -eq 'FAIL'}).Count
$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}elseif($fail){0}else{1}
@{status=$validity;score=$score;testcase_total=$Cases.Count;testcase_pass_count=($Cases.Count-$fail);testcases=$Cases}|ConvertTo-Json -Depth 15|Set-Content -LiteralPath (Join-Path $OutputRoot 'report.json') -Encoding utf8
$ctests=@($Cases|ForEach-Object {@{name=$_.id;status=$(if($_.status -eq 'PASS'){'passed'}else{'failed'});duration=$_.duration_ms;message=$_.details;extra=@{group=$_.group;classification=$_.classification;required=$true}}})
@{results=@{tool=@{name='Windows Registry Harbor verifier';version='1.1.10'};summary=@{tests=$Cases.Count;passed=($Cases.Count-$fail);failed=$fail;pending=0;skipped=0;other=0;start=$StartedAt;stop=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()};tests=$ctests;extra=@{validity=$validity;score=$score;scoring='all_required_pass'}}}|ConvertTo-Json -Depth 15|Set-Content -LiteralPath (Join-Path $OutputRoot 'ctrf.json') -Encoding utf8
$stats=@{testcase_total=$Cases.Count;Explicit=@($Cases|Where-Object classification -eq 'Explicit').Count;Implicit=@($Cases|Where-Object classification -eq 'Implicit').Count;F2P=@($Cases|Where-Object group -eq 'F2P').Count;P2P=@($Cases|Where-Object group -eq 'P2P').Count;rubric_entries=$manifest.Count;boundary_subcases=12;invalid=$invalid;range_note='31 independent cases retained under user exemption; no valid tests deleted to meet 5-20 or preferred 5-27.'}
$stats|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $OutputRoot 'statistics.json') -Encoding utf8
Write-Host "AGGREGATE validity=$validity score=$score passed=$($Cases.Count-$fail) total=$($Cases.Count) Explicit=$($stats.Explicit) Implicit=$($stats.Implicit) F2P=$($stats.F2P) P2P=$($stats.P2P)"
if($invalid){throw 'Required testcase set incomplete or invalid; INVALID/null'}
@{reward=$score}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $OutputRoot 'reward.json') -Encoding utf8
exit 0
