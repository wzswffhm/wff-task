[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ResultsDir,
    [string]$RubricPath = '',
    [string]$TaskId = 'windows-d4-litemonitor-001',
    [string]$TaskVersion = '2.1.2',
    [string]$RunId = '',
    [string]$RepoCommit = '',
    [string]$BaseImageDigest = '',
    [string]$InvalidReason = '',
    [string]$BuildInfoPath = '',
    [string]$RequestedSuites = 'all'
)
$ErrorActionPreference = 'Stop'
if (-not $RubricPath) { $RubricPath = Join-Path $PSScriptRoot 'rubric.json' }
$issues = New-Object System.Collections.Generic.List[string]
$observed = @{}
$cases = @()
if ($InvalidReason) { $issues.Add($InvalidReason) }
if ($RequestedSuites -ne 'all') { $issues.Add('Partial suite execution cannot receive a formal score.') }
New-Item -ItemType Directory -Path $ResultsDir -Force | Out-Null
try {
    $rubric = Get-Content -LiteralPath $RubricPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($rubric.task_id -ne $TaskId -or $rubric.task_version -ne $TaskVersion) { throw 'Rubric identity mismatch.' }
    $required = @($rubric.required_tests)
    if ($required.Count -eq 0) { throw 'Empty required testcase manifest.' }
    if (@($required.id | Select-Object -Unique).Count -ne $required.Count) { throw 'Duplicate required testcase ID.' }
    foreach ($suite in @('fail_to_pass','pass_to_pass','system_state')) {
        $path = Join-Path $ResultsDir "suite_$suite.json"
        try {
            $payload = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($payload.task_id -ne $TaskId -or $payload.task_version -ne $TaskVersion -or $payload.run_id -ne $RunId) { throw "Suite identity mismatch: $suite" }
            foreach ($check in @($payload.checks)) {
                $identifier = [string]$check.id
                if ($observed.ContainsKey($identifier)) { $issues.Add("Duplicate testcase: $identifier"); continue }
                if ($identifier -notin $required.id) { $issues.Add("Unexpected testcase: $identifier") }
                if ($check.suite -ne $suite) { $issues.Add("Wrong suite: $identifier") }
                $observed[$identifier] = $check
            }
        } catch { $issues.Add($_.Exception.Message) }
    }
    foreach ($expected in $required) {
        $check = $observed[[string]$expected.id]
        $state = 'MISSING'
        $detail = 'Required testcase was not reported.'
        if ($null -ne $check) {
            $state = ([string]$check.status).ToUpperInvariant()
            $detail = [string]$check.detail
            if ($state -eq 'INVALID') { $state = 'ERROR' }
            if ($check.suite -ne $expected.suite) { $issues.Add("Manifest suite mismatch: $($expected.id)") }
            if (($state -eq 'PASS' -and $check.passed -ne $true) -or ($state -eq 'FAIL' -and $check.passed -ne $false)) { $issues.Add("Inconsistent verdict: $($expected.id)") }
        }
        if ($state -notin @('PASS','FAIL')) { $issues.Add("$($expected.id): $state") }
        $cases += [ordered]@{ id=$expected.id; group=$expected.group; suite=$expected.suite; status=$state; detail=$detail }
    }
} catch { $issues.Add($_.Exception.Message) }
$residue = $null
try {
    $cleanup = Get-Content -LiteralPath (Join-Path $ResultsDir 'cleanup_report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cleanup.task_id -ne $TaskId -or $cleanup.run_id -ne $RunId) { throw 'Cleanup identity mismatch.' }
    $residue = $cleanup.residue_count
    if ($null -eq $residue -or [int]$residue -ne 0) { throw 'Cleanup did not prove zero residue.' }
} catch { $issues.Add($_.Exception.Message) }
$score = $null
$validity = 'INVALID'
$status = 'INVALID'
if ($issues.Count -eq 0 -and $cases.Count -gt 0) {
    $validity = 'VALID'
    $score = [int](@($cases | Where-Object { $_.status -ne 'PASS' }).Count -eq 0)
    $status = if ($score -eq 1) { 'RESOLVED' } else { 'FAILED' }
}
$result = [ordered]@{
    task_id=$TaskId; task_version=$TaskVersion; run_id=$RunId
    validity=$validity; status=$status; score=$score; reward=$score; programmatic_score=$score
    resolved=($score -eq 1); tests_total=$cases.Count
    tests_passed=@($cases | Where-Object { $_.status -eq 'PASS' }).Count
    tests_failed=@($cases | Where-Object { $_.status -eq 'FAIL' }).Count
    invalid_reason=($issues -join ' | '); checks=$cases; residue_count=$residue
    repo_commit=$RepoCommit; base_image_digest=$BaseImageDigest
    aggregated_at_utc=[DateTime]::UtcNow.ToString('o')
}
$encoding = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText((Join-Path $ResultsDir 'result.json'), ($result | ConvertTo-Json -Depth 12), $encoding)
[IO.File]::WriteAllText((Join-Path $ResultsDir 'reward.json'), (@{reward=$score} | ConvertTo-Json), $encoding)
[IO.File]::WriteAllText((Join-Path $ResultsDir 'system_state.json'), (@{residue_count=$residue; validity=$validity} | ConvertTo-Json), $encoding)
$xml = New-Object System.Xml.XmlDocument
$root = $xml.CreateElement('testsuite')
$root.SetAttribute('name',$TaskId)
$root.SetAttribute('tests',[string]$cases.Count)
[void]$xml.AppendChild($root)
foreach ($case in $cases) {
    $node = $xml.CreateElement('testcase')
    $node.SetAttribute('name',[string]$case.id)
    $node.SetAttribute('classname',[string]$case.group)
    if ($case.status -ne 'PASS') {
        $kind = if ($case.status -eq 'FAIL') { 'failure' } else { 'error' }
        $failure = $xml.CreateElement($kind)
        $failure.InnerText = [string]$case.detail
        [void]$node.AppendChild($failure)
    }
    [void]$root.AppendChild($node)
}
$xml.Save((Join-Path $ResultsDir 'junit.xml'))
Write-Host "STATUS=$status SCORE=$score PASS=$($result.tests_passed)/$($cases.Count)"
if ($validity -eq 'INVALID') { Write-Host $result.invalid_reason; exit 2 }
exit 0
