function Merge-RuntimeReports {
    param([Parameter(Mandatory)]$Reports, [Parameter(Mandatory)]$Rubric)
    if (@($Reports).Count -ne 2) { throw 'Exactly two runtime reports required' }
    $ids = @($reports[0].checks | ForEach-Object { $_.test_id })
    $otherIds = @($reports[1].checks | ForEach-Object { $_.test_id })
    if ($ids.Count -eq 0 -or $ids.Count -ne @($ids | Select-Object -Unique).Count -or
        $otherIds.Count -ne $ids.Count -or @(Compare-Object $ids $otherIds).Count -gt 0) {
        throw 'Runtime matrix testcase evidence differs'
    }
    $checks = foreach ($first in $reports[0].checks) {
        $second = @($reports[1].checks | Where-Object { $_.test_id -eq $first.test_id })[0]
        [pscustomobject]@{ test_id = $first.test_id; category = $first.category;
            passed = [bool]($first.passed -and $second.passed);
            failure_reason = ((@($first.failure_reason, $second.failure_reason) | Where-Object { $_ }) -join '; ') }
    }
    # Binary scoring (Windows 专项 Coding Bench 数据 6.2): no weights, no partial credit.
    # The rubric is reporting metadata only and carries no weight.
    $rubricBreakdown = foreach ($item in $rubric.items) {
        $required = @(@($item.test_ids) + @($item.requires_test_ids) | Where-Object { $_ })
        $bad = @($required | Where-Object { $id = $_; -not @($checks | Where-Object { $_.test_id -eq $id -and $_.passed }).Count })
        [pscustomobject]@{ rubric_id = [string]$item.rubric_id; passed = ($bad.Count -eq 0); test_ids = @($item.test_ids) }
    }
    $failed = @($checks | Where-Object { -not $_.passed })
    $binaryReward = [int]($checks.Count -gt 0 -and $failed.Count -eq 0)
    $result = [ordered]@{ task_id = 'windows-powershell-ads-001'; status = $(if ($failed.Count) { 'FAILED' } else { 'RESOLVED' });
        reward = $binaryReward; programmatic_score = $binaryReward; resolved = ($failed.Count -eq 0);
        score_method = 'binary_all_required'; partial_credit = $false;
        rubric_breakdown = @($rubricBreakdown);
        tests_total = $checks.Count; tests_failed = $failed.Count; tests_passed = $checks.Count - $failed.Count;
        checks = @($checks); runtime_matrix = @('windows-powershell-5.1', 'powershell-7');
        runtime_evidence = @('windows-powershell-5.1/result.json', 'powershell-7/result.json') }
    return [pscustomobject]$result
}
