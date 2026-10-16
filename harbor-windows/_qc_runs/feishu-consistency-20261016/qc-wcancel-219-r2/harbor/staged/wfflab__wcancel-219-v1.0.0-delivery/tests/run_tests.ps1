# Generated for wfflab__wcancel-219 by the task authoring pipeline.
#
# Objective checks for the wcancel overlapped-I/O cancellation contract. The hidden
# semantic suite is injected by the evaluation side and executed against the
# candidate package with pytest; its per-test outcome is mapped onto stable
# check ids. Scoring is delegated to aggregate_results.ps1.
#
# The suite is deliberately NOT part of this package: it is resolved from a
# verifier-side root. See agent_visible_paths.json.
#
# Exit codes:
#   0  every check passed
#   1  at least one check failed (functional failure)
#   2  the harness itself could not run (infrastructure failure)

[CmdletBinding()]
param(
    [string]$WorkspaceRoot = '',
    [string]$ChecksPath = '',
    [string]$TaskRoot = '',
    [string]$VerifierRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { $WorkspaceRoot = Join-Path $TaskRoot 'environment\workspace' }
if ([string]::IsNullOrWhiteSpace($ChecksPath)) { $ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json') }

function Resolve-HiddenSuite([string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Root)) { return '' }
    foreach ($relative in @('tests\test_wcancel_semantics.py', 'test_wcancel_semantics.py')) {
        $candidate = Join-Path $Root $relative
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return ''
}

$verifierCandidates = New-Object System.Collections.ArrayList
if (-not [string]::IsNullOrWhiteSpace($VerifierRoot)) { [void]$verifierCandidates.Add($VerifierRoot) }
if (-not [string]::IsNullOrWhiteSpace($env:WCANCEL_VERIFIER_ROOT)) { [void]$verifierCandidates.Add($env:WCANCEL_VERIFIER_ROOT) }
[void]$verifierCandidates.Add('C:\verifier\wfflab__wcancel-219')
[void]$verifierCandidates.Add('C:\verifier')
# Harbor copies tests/ into the container at C:\tests for the verifier step (and
# only for that step), so the hidden suite also ships next to the scoring entry
# point. The two copies must stay byte-identical; see verifier/README.md.
[void]$verifierCandidates.Add('C:\tests')
$packageRoot = Split-Path -Parent $TaskRoot
if (-not [string]::IsNullOrWhiteSpace($packageRoot)) {
    [void]$verifierCandidates.Add((Join-Path $packageRoot 'outside_harbor-verifier\wfflab__wcancel-219'))
}

$hiddenSuite = ''
foreach ($candidate in $verifierCandidates) {
    $hiddenSuite = Resolve-HiddenSuite $candidate
    if (-not [string]::IsNullOrWhiteSpace($hiddenSuite)) { break }
}

# ---- infrastructure preconditions -----------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $WorkspaceRoot 'wcancel') '__init__.py'))) {
    Write-Host "INVALID: candidate package not found under $WorkspaceRoot"
    exit 2
}
if ([string]::IsNullOrWhiteSpace($hiddenSuite)) {
    Write-Host 'INVALID: the verifier-side hidden semantic suite was not injected'
    exit 2
}
Write-Host "verifier: hidden suite resolved to $hiddenSuite"

# The graded suite runs against a scratch copy so that pytest artefacts never
# touch the (possibly read-only) workspace and so a stale cache cannot leak in.
$runRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('wcancel-graded-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null

try {
    & robocopy $WorkspaceRoot $runRoot /E /XD .git __pycache__ .pytest_cache reports /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "INVALID: staging the candidate workspace failed (robocopy $LASTEXITCODE)"
        exit 2
    }
    $global:LASTEXITCODE = 0

    $testsDir = Join-Path $runRoot 'tests'
    if (-not (Test-Path -LiteralPath $testsDir)) { New-Item -ItemType Directory -Path $testsDir -Force | Out-Null }
    Copy-Item -LiteralPath $hiddenSuite -Destination (Join-Path $testsDir 'test_wcancel_semantics.py') -Force

    # The embed interpreter isolates sys.path through python312._pth, so PYTHONPATH
    # alone is not enough. Drop a conftest that prepends the scratch root so that
    # `import wcancel` resolves against the staged candidate package.
    $conftest = @'
import pathlib
import sys

_root = str(pathlib.Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
'@
    Set-Content -LiteralPath (Join-Path $runRoot 'conftest.py') -Value $conftest -Encoding UTF8

    $reportPath = Join-Path $runRoot ('pytest-results' + '.json')
    $python = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
    if (-not $python) {
        Write-Host 'INVALID: no python interpreter is available on PATH'
        exit 2
    }

    $env:PYTHONPATH = "$runRoot;$env:PYTHONPATH"
    Push-Location -LiteralPath $runRoot
    try {
        & $python.Source -m pytest -rA --tb=short -p no:cacheprovider --json-report --json-report-file=$reportPath (Join-Path 'tests' 'test_wcancel_semantics.py') 2>&1 | Out-Host
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $reportPath)) {
        Write-Host 'INVALID: pytest produced no json report'
        exit 2
    }

    $doc = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json

    # Map the pytest node ids onto the stable contract check ids.
    $slugByFunction = [ordered]@{
        'test_cancel_affects_only_the_target_request'        = 'cancel-affects-only-the-target-request'
        'test_cancel_works_from_another_thread'              = 'cancel-works-from-another-thread'
        'test_uncancelled_request_still_delivers_the_bytes'  = 'uncancelled-request-still-delivers-the-bytes'
        'test_cancelled_request_reports_cancelled_status'    = 'cancelled-request-reports-cancelled-status'
        'test_completed_request_cannot_be_cancelled'         = 'completed-request-cannot-be-cancelled'
        'test_second_cancel_reports_false'                   = 'second-cancel-reports-false'
        'test_non_overlapped_handle_is_unsupported'          = 'non-overlapped-handle-is-unsupported'
        'test_submit_leaves_request_pending'                 = 'submit-leaves-request-pending'
        'test_cancel_returns_a_bool'                         = 'cancel-returns-a-bool'
        'test_wait_returns_a_completion'                     = 'wait-returns-a-completion'
        'test_wait_timeout_raises_timeout_kind'              = 'wait-timeout-raises-timeout-kind'
        'test_invalid_handle_is_rejected'                    = 'invalid-handle-is-rejected'
        'test_cancel_all_cancels_every_submitted_request'    = 'cancel-all-cancels-every-submitted-request'
        'test_visible_smoke_suite_still_passes'              = 'visible-smoke-suite-still-passes'
    }

    # Map the pytest outcome onto the contract status. Anything that is neither a
    # clean pass nor a clean failure means the harness could not observe the case
    # (pytest error, skip, or a missing collection): that is INVALID and must not
    # be reported as a candidate score of 0.
    $observed = @{}
    foreach ($test in @($doc.tests)) {
        $nodeId = [string]$test.nodeid
        if ([string]::IsNullOrWhiteSpace($nodeId)) { continue }
        $function = ($nodeId -split '::')[-1]
        if (-not $slugByFunction.Contains($function)) { continue }
        $slug = [string]$slugByFunction[$function]
        $outcome = ([string]$test.outcome).ToLowerInvariant()
        if ($outcome -eq 'passed' -or $outcome -eq 'xpassed') { $status = 'PASS' }
        elseif ($outcome -eq 'failed') { $status = 'FAIL' }
        else { $status = 'INVALID' }
        $observed[$slug] = @{ Status = $status; Detail = "pytest outcome=$outcome" }
    }

    $collected = @($doc.tests).Count

    $results = New-Object System.Collections.ArrayList
    foreach ($entry in $slugByFunction.GetEnumerator()) {
        $slug = [string]$entry.Value
        if ($observed.ContainsKey($slug)) {
            $state = $observed[$slug]
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = $state.Status; detail = $state.Detail })
        }
        else {
            # A required case the suite never reported. When the suite collected
            # nothing at all, the candidate package could not even be imported at
            # grading time: that is a functional failure of the candidate. A
            # partial collection is a harness fault and must stay INVALID.
            if ($collected -eq 0) {
                [void]$results.Add([pscustomobject][ordered]@{
                        test_id = $slug
                        status  = 'FAIL'
                        detail  = 'the suite collected no case at all; the candidate package could not be imported'
                    })
            }
            else {
                [void]$results.Add([pscustomobject][ordered]@{
                        test_id = $slug
                        status  = 'INVALID'
                        detail  = 'required check was not collected'
                    })
            }
        }
    }

    $checksDirectory = Split-Path -Parent $ChecksPath
    if (-not (Test-Path -LiteralPath $checksDirectory)) { New-Item -ItemType Directory -Path $checksDirectory -Force | Out-Null }

    $payload = [pscustomobject][ordered]@{
        task_id      = 'wfflab__wcancel-219'
        task_version = '1.0.0'
        checks       = @($results.ToArray())
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ChecksPath -Encoding UTF8

    $passed = @($results | Where-Object { $_.status -eq 'PASS' }).Count
    $failed = @($results | Where-Object { $_.status -eq 'FAIL' }).Count
    $invalid = @($results | Where-Object { $_.status -eq 'INVALID' }).Count
    Write-Host ("checks: {0} passed, {1} failed, {2} invalid, {3} total" -f $passed, $failed, $invalid, $results.Count)

    if ($invalid -gt 0) {
        Write-Host ("INVALID: {0} required check(s) were not observed; incomplete evidence is never a candidate score" -f $invalid)
        exit 2
    }
    if ($failed -gt 0) { exit 1 }
    exit 0
}
finally {
    if (Test-Path -LiteralPath $runRoot) { Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
