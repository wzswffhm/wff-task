# Keep disk headroom while model rounds run.
#
# Every Harbor job leaves behind an env image around 10 GB and Harbor does not
# clean them up, so six rounds would need roughly 60 GB against ~23 GB free.
# Prune finished job images whenever free space drops, always keeping the newest
# two so nothing still in use is touched (docker refuses to remove an in-use
# image anyway, so this is safe).

$ErrorActionPreference = 'Continue'

$stage = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wtoken-build\model-rounds'
$deadline = (Get-Date).AddHours(4)
$round = 0

Write-Host 'monitoring disk while model rounds run'

while ((Get-Date) -lt $deadline) {
    $round++
    Start-Sleep -Seconds 120

    $free = (Get-PSDrive C).Free / 1GB
    $harbor = @(Get-Process harbor -ErrorAction SilentlyContinue).Count

    if ($round % 5 -eq 0 -or $free -lt 10) {
        Write-Host ("  [{0}] free {1:N1} GB, harbor procs {2}" -f (Get-Date).ToString('HH:mm:ss'), $free, $harbor)
    }

    if ($free -lt 10) {
        Write-Host '  low space: pruning oldest job images'
        $rows = @(docker --context desktop-windows images --format '{{.Repository}}|{{.ID}}|{{.Size}}' 2>&1 |
                  Where-Object { $_ -match 'wtoken-221-v1-0-0-delive__' })
        if ($rows.Count -gt 2) {
            $rows | Select-Object -SkipLast 2 | ForEach-Object {
                $parts = $_ -split '\|'
                docker --context desktop-windows rmi -f $parts[1] 2>&1 | Out-Null
                Write-Host ("    removed " + $parts[0])
            }
        }
        $after = (Get-PSDrive C).Free / 1GB
        Write-Host ("    free now {0:N1} GB" -f $after)
    }

    # Stop once the rounds directory holds all twelve trials and nothing is running.
    if ($harbor -eq 0 -and (Test-Path -LiteralPath $stage)) {
        $trials = @(Get-ChildItem -LiteralPath $stage -Directory -ErrorAction SilentlyContinue).Count
        if ($trials -ge 6) {
            Write-Host ("  all $trials model rounds present and no harbor process is running")
            break
        }
    }
}

Write-Host '--- model round results ---'
if (Test-Path -LiteralPath $stage) {
    Get-ChildItem -LiteralPath $stage -Directory | Sort-Object Name | ForEach-Object {
        $result = Join-Path $_.FullName 'result.json'
        $reward = '?'
        if (Test-Path -LiteralPath $result) {
            try {
                $doc = Get-Content -LiteralPath $result -Raw -Encoding UTF8 | ConvertFrom-Json
                $reward = $doc.verifier_result.rewards.reward
            } catch { $reward = 'parse-error' }
        }
        Write-Host ("  {0,-18} reward={1}" -f $_.Name, $reward)
    }
}
Write-Host ("disk free: {0:N1} GB" -f ((Get-PSDrive C).Free / 1GB))
