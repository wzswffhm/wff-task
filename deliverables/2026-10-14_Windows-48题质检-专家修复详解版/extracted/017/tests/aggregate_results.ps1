param([string]$ResultPath)
$r=Get-Content -LiteralPath $ResultPath -Raw|ConvertFrom-Json
$expected=(Get-Content (Join-Path $PSScriptRoot 'rubric.json') -Raw|ConvertFrom-Json).required
$actual=@($r.testcases);$invalid=$actual.Count-ne $expected.Count
foreach($e in $expected){$a=@($actual|Where-Object id -eq $e.id);if($a.Count-ne 1-or $a[0].group-ne $e.group-or $a[0].status-notin @('PASS','FAIL')){$invalid=$true}}
if($invalid){if($r.validity-ne 'INVALID'-or $null-ne $r.score){throw 'Infrastructure must be INVALID/null'}}else{$score=[int](@($actual|Where-Object status -ne 'PASS').Count-eq 0);if($r.score-ne $score-or $r.validity-ne 'VALID'){throw 'Score mismatch'}}
$r
