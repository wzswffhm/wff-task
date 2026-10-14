param([string]$Logs = 'C:\logs\verifier', [string]$Results = '')
$ErrorActionPreference = 'Stop'
if (-not $Results) { $Results = Join-Path $Logs 'results.json' }
if (-not (Test-Path -LiteralPath $Results)) { '{"validity":"INVALID","score":null}' ; exit 2 }
try { $r = Get-Content -LiteralPath $Results -Raw -Encoding UTF8 | ConvertFrom-Json } catch { '{"validity":"INVALID","score":null}' ; exit 2 }
$required = @($r.required); $cases = @($r.testcases)
if ($required.Count -eq 0 -or $cases.Count -ne $required.Count) { '{"validity":"INVALID","score":null}' ; exit 2 }
$ids = @($cases | ForEach-Object { $_.id }); if (@($ids | Select-Object -Unique).Count -ne $ids.Count) { '{"validity":"INVALID","score":null}' ; exit 2 }
if (@($cases | Where-Object { $_.status -notin @('PASS','FAIL') }).Count -gt 0) { '{"validity":"INVALID","score":null}' ; exit 2 }
$score = if (@($cases | Where-Object status -ne PASS).Count -eq 0) { 1 } else { 0 }
[pscustomobject]@{ validity='VALID'; score=$score; testcase_pass_count=@($cases | Where-Object status -eq PASS).Count; testcase_total=$cases.Count; required=$required; testcases=$cases } | ConvertTo-Json -Depth 12 -Compress
exit 0
