# tests/test.ps1 —— 验证入口（Windows 版）
#
# 职责顺序（不可颠倒）：
#   1. 还原被 test_patch 触碰的文件（从 HEAD 恢复 / 删除新增文件）
#   2. apply test_patch（先 --check --binary）
#   3. 环境预检（证明 prepared environment 真的可用）
#   4. 清除旧产物（防止复用旧 report）
#   5. 运行 required 测试
#   6. 调用 grade.py 评分
#   7. 校验评分产物完整性
#
# 核心原则：模型测试失败 = 合法 0 分；缺失/损坏的评分产物 = 基础设施故障 = INVALID

$ErrorActionPreference = 'Continue'
$tests = 'C:\tests'; $logs = 'C:\logs'
New-Item -ItemType Directory -Force "$logs\verifier" | Out-Null
Remove-Item "$logs\verifier\reward.txt", "$logs\verifier\reward.json", "$logs\verifier\reward-details.json" -Force -ErrorAction SilentlyContinue

# ---- 1. 还原 test_patch 触碰的文件 ----
Set-Location C:\testbed
$patch = Join-Path $tests 'test_patch.diff'
if ((Test-Path $patch) -and ((Get-Item $patch).Length -gt 0)) {
  $trackedPaths = Select-String -Path $patch -Pattern '^--- a/(.*)$' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Where-Object { $_ -ne '/dev/null' }
  foreach ($f in $trackedPaths) {
    git restore --source=HEAD --staged --worktree -- $f 2>$null
    if ($LASTEXITCODE -ne 0) { git checkout HEAD -- $f 2>$null }
  }
  $newPaths = Select-String -Path $patch -Pattern '^\+\+\+ b/(.*)$' | ForEach-Object { $_.Matches[0].Groups[1].Value }
  foreach ($f in $newPaths) {
    & git ls-files --error-unmatch -- $f 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0 -and (Test-Path -LiteralPath $f)) { Remove-Item -LiteralPath $f -Force }
  }
}

# ---- 2. apply test_patch ----
if ((Test-Path $patch) -and ((Get-Item $patch).Length -gt 0)) {
  $check = (& git apply --check --binary --whitespace=nowarn $patch 2>&1 | Out-String)
  if ($LASTEXITCODE -ne 0) { Write-Output '===SWELIVE_INVALID test_patch_check_failed==='; Write-Output $check; exit 2 }
  & git apply --binary --whitespace=nowarn $patch
  if ($LASTEXITCODE -ne 0) { Write-Output '===SWELIVE_INVALID test_patch_apply_failed==='; exit 2 }
}

# ---- 3. 环境预检 ----
Set-Location C:\testbed
$env:PYTHONPATH = "C:\testbed;$env:PYTHONPATH"
python -c "import pytest, wtask"
if ($LASTEXITCODE -ne 0) { Write-Output '===SWELIVE_INVALID prepared_environment_missing==='; exit 2 }

# ---- 4/5. 清除旧产物并运行 required 测试 ----
$log = Join-Path $env:TEMP 'swelive_test.log'
Remove-Item reports -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force reports | Out-Null
python -m pytest -rA --tb=short -p no:cacheprovider --json-report --json-report-file=reports\pytest-results.json tests\test_wtask_semantics.py
$testRc = $LASTEXITCODE
if (-not (Test-Path reports\pytest-results.json)) { Write-Output '===SWELIVE_INVALID test_report_missing==='; exit 2 }
& { Get-Content -Raw reports\pytest-results.json } 2>&1 | Out-File -Encoding utf8 $log
# pytest 退出码：0=全通过，1=存在测试失败（这是候选的合法 0 分）。
# >1 表示中断 / 内部错误 / 用法错误 / 没有收集到测试，属于候选级故障。
if ($testRc -gt 1) { Add-Content -Encoding utf8 $log '===SWELIVE_CANDIDATE_FAILURE compile_or_test_collection_failed===' }

Write-Output '===SWELIVE_LOG_BEGIN==='
if (Test-Path $log) { Get-Content -Raw $log } else { Write-Output '[missing log]' }
Write-Output '===SWELIVE_LOG_END==='

# ---- 6. 评分 ----
$py = $null
if (Test-Path 'C:\Python312\python.exe') { $py = Get-Command 'C:\Python312\python.exe' }
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if ($py) { & $py.Source "$tests\grade.py" "$log" "$logs"; Write-Output "===SWELIVE_GRADE rc=$LASTEXITCODE test_rc=$testRc===" }

# ---- 7. 评分产物完整性 ----
$rewardTxt = Join-Path $logs 'verifier\reward.txt'
$rewardJson = Join-Path $logs 'verifier\reward.json'
$rewardDetails = Join-Path $logs 'verifier\reward-details.json'
if (-not (Test-Path $rewardTxt) -or -not (Test-Path $rewardJson) -or -not (Test-Path $rewardDetails)) {
  Write-Output '===SWELIVE_INVALID reward_artifact_missing==='
  exit 2
}
try {
  $score = [double]::Parse((Get-Content -Raw $rewardTxt).Trim(), [Globalization.CultureInfo]::InvariantCulture)
  $jsonScore = [double]((Get-Content -Raw $rewardJson | ConvertFrom-Json).reward)
  $details = Get-Content -Raw $rewardDetails | ConvertFrom-Json
  if ([double]::IsNaN($score) -or [double]::IsInfinity($score) -or $score -lt 0 -or $score -gt 1) { throw 'reward.txt out of range' }
  if ([math]::Abs($score - $jsonScore) -gt 0.0000001) { throw 'reward files disagree' }
  if ($null -eq $details.reward -or @($details.reward).Count -lt 1) { throw 'reward-details.json has no criteria' }
} catch {
  Write-Output ('===SWELIVE_INVALID reward_artifact_malformed=== ' + $_.Exception.Message)
  exit 2
}
exit 0
