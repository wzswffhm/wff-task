[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ResultPath
)

$result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
if ($result.status -eq 'INVALID') {
    [pscustomobject]@{
        status = 'INVALID'
        resolved = $false
        score = 0.0
        reason = $result.invalid_reason
    } | ConvertTo-Json -Depth 4
    exit 2
}

$rubric = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'rubric.json') -Raw | ConvertFrom-Json
$rubricBreakdown = foreach ($item in $rubric.items) {
    $passed = $true
    $requiredIds = if ($item.PSObject.Properties.Name -contains 'requires_test_ids') { @($item.requires_test_ids) } else { @() }
    $boundTestIds = @($item.test_ids) + $requiredIds
    foreach ($testId in $boundTestIds) {
        $check = @($result.checks | Where-Object { $_.test_id -eq $testId })
        if ($check.Count -ne 1 -or -not $check[0].passed) {
            $passed = $false
        }
    }
    [pscustomobject]@{ rubric_id = [string]$item.rubric_id; passed = $passed; test_ids = @($item.test_ids) }
}
# Binary scoring: no weights, no partial credit.
$failedChecks = @($result.checks | Where-Object { -not $_.passed })
$score = if ($result.checks.Count -gt 0 -and $failedChecks.Count -eq 0 -and $result.status -ne 'INVALID') { 1 } else { 0 }

[pscustomobject]@{
    status = $result.status
    resolved = [bool]$result.resolved
    score = $score
    score_rule = 'binary_all_required'
    rubric_breakdown = @($rubricBreakdown)
    tests_total = $result.tests_total
    tests_failed = $result.tests_failed
} | ConvertTo-Json -Depth 4
