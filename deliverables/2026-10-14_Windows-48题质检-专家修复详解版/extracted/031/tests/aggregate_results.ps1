param([string]$ResultPath)
$r=Get-Content -LiteralPath $ResultPath -Raw|ConvertFrom-Json;$expected=(Get-Content -LiteralPath (Join-Path $PSScriptRoot 'rubric.json') -Raw|ConvertFrom-Json).required;$a=@($r.testcases)
if($a.Count-ne $expected.Count){throw 'Missing required testcase'}
foreach($e in $expected){$x=@($a|Where-Object id -eq $e.id);if($x.Count-ne 1-or $x[0].group-ne $e.group-or $x[0].status-notin @('PASS','FAIL')){throw 'Invalid required testcase'}}
$score=[int](@($a|Where-Object status -ne 'PASS').Count-eq 0);if($r.validity-ne 'VALID'-or $r.score-ne $score){throw 'Binary score mismatch'};$r
