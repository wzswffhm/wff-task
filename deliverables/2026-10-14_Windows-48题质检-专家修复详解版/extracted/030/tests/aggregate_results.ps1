param([Parameter(Mandatory)][string]$ResultPath)
$r=Get-Content -LiteralPath $ResultPath -Raw|ConvertFrom-Json
if($r.validity-ne 'VALID'){exit 2};if($r.score-eq 1){exit 0};exit 1
