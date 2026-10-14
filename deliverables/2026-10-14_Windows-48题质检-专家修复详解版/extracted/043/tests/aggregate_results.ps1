param([string]$ResultPath)
$r=Get-Content -LiteralPath $ResultPath -Raw|ConvertFrom-Json;$required=(Get-Content (Join-Path $PSScriptRoot 'rubric.json') -Raw|ConvertFrom-Json).required
if(@($r.testcases).Count-ne $required.Count){throw 'Missing testcase'}
foreach($e in $required){$a=@($r.testcases|Where-Object id -eq $e.id);if($a.Count-ne 1-or $a[0].group-ne $e.group-or $a[0].status-notin @('PASS','FAIL')){throw 'Invalid testcase'}}
$s=[int](@($r.testcases|Where-Object status -ne 'PASS').Count-eq 0);if($r.validity-ne 'VALID'-or $r.score-ne $s){throw 'Score mismatch'};$r
