param([string]$CasePath)
$ErrorActionPreference='Stop'
$c=Get-Content -LiteralPath $CasePath -Raw|ConvertFrom-Json
$watch=[Diagnostics.Stopwatch]::StartNew();$r=@{}
try{$r.records=@(& $c.candidate -PipeName $c.pipe -Messages ([string[]]$c.messages) -TimeoutMs $c.timeout)}catch{$r.error=$_.Exception.Message}
$r.elapsed_ms=$watch.ElapsedMilliseconds
$r|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $c.client_result -Encoding utf8
