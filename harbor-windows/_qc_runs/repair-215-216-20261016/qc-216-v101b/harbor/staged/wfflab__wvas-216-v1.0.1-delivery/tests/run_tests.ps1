# Generated for wfflab__wvas-216 by the task authoring pipeline.
#
# Objective checks for the wvas address-space contract. The hidden semantic
# suite is injected by the evaluation side and executed against the candidate
# package with pytest; its per-test outcome is mapped onto stable check ids.
# Scoring is delegated to aggregate_results.ps1.
#
# The suite is deliberately NOT part of this package: it is resolved from a
# verifier-side root. See environment/agent_visible_paths.json.
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
    foreach ($relative in @('tests\test_wvas_semantics.py', 'test_wvas_semantics.py')) {
        $candidate = Join-Path $Root $relative
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return ''
}

$verifierCandidates = New-Object System.Collections.ArrayList
if (-not [string]::IsNullOrWhiteSpace($VerifierRoot)) { [void]$verifierCandidates.Add($VerifierRoot) }
if (-not [string]::IsNullOrWhiteSpace($env:WVAS_VERIFIER_ROOT)) { [void]$verifierCandidates.Add($env:WVAS_VERIFIER_ROOT) }
[void]$verifierCandidates.Add('C:\verifier\wfflab__wvas-216')
[void]$verifierCandidates.Add('C:\verifier')
# Harbor copies tests/ into the container at C:\tests for the verifier step (and
# only for that step), so the hidden suite also ships next to the scoring entry
# point. The two copies must stay byte-identical; see verifier/README.md.
[void]$verifierCandidates.Add('C:\tests')
$packageRoot = Split-Path -Parent $TaskRoot
if (-not [string]::IsNullOrWhiteSpace($packageRoot)) {
    [void]$verifierCandidates.Add((Join-Path $packageRoot 'outside_harbor-verifier\wfflab__wvas-216'))
}

$hiddenSuite = ''
foreach ($candidate in $verifierCandidates) {
    $hiddenSuite = Resolve-HiddenSuite $candidate
    if (-not [string]::IsNullOrWhiteSpace($hiddenSuite)) { break }
}

# ---- infrastructure preconditions -----------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $WorkspaceRoot 'wvas') '__init__.py'))) {
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
$runRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('wvas-graded-' + [Guid]::NewGuid().ToString('N'))
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
    Copy-Item -LiteralPath $hiddenSuite -Destination (Join-Path $testsDir 'test_wvas_semantics.py') -Force

    # The embed interpreter isolates sys.path through python312._pth, so PYTHONPATH
    # alone is not enough. Drop a conftest that prepends the scratch root so that
    # `import wvas` resolves against the staged candidate package, and that mirrors
    # every per-case outcome onto the trusted channel described below.
    $conftest = @'
import json
import os
import pathlib
import sys

_root = str(pathlib.Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

_MARK = "##WFF-OBS##"
_NONCE = os.environ.get("WFF_GRADING_NONCE", "")
_SUITE = os.environ.get("WFF_GRADING_SUITE", "")
# One of the contract cases below runs the visible smoke suite in a child pytest
# process. That child inherits this conftest and would mirror the smoke cases
# onto the trusted channel, where a same-named case would look like a second
# report of a contract case. Only the process that was actually pointed at the
# hidden suite may speak on the channel.
_ACTIVE = bool(_SUITE) and any(str(arg).endswith(_SUITE) for arg in sys.argv)


def _emit(report):
    payload = {
        "nonce": _NONCE,
        "nodeid": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
    }
    stream = getattr(sys, "__stdout__", None) or sys.stdout
    stream.write("%s%s\n" % (_MARK, json.dumps(payload, sort_keys=True)))
    stream.flush()


def pytest_runtest_logreport(report):
    if not _ACTIVE:
        return
    # A call report carries the verdict; a non-passing setup or teardown report
    # carries the harness fault. Nothing else is worth mirroring.
    if report.when == "call" or report.outcome != "passed":
        try:
            _emit(report)
        except Exception:
            pass
'@
    Set-Content -LiteralPath (Join-Path $runRoot 'conftest.py') -Value $conftest -Encoding UTF8

    $reportPath = Join-Path $runRoot ('pytest-results' + '.json')
    $python = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
    if (-not $python) {
        Write-Host 'INVALID: no python interpreter is available on PATH'
        exit 2
    }

    # ---- harness self-check (trusted side; never imports the candidate) ------
    # A missing pytest or a missing json-report plugin means the graded suite
    # cannot be observed at all. That is an infrastructure fault and must be
    # reported as INVALID, never as a candidate score of 0.
    $selfCheck = & $python.Source -c "import pytest, pytest_jsonreport; print('HARNESS-OK')" 2>&1 | Out-String
    if ($selfCheck -notmatch 'HARNESS-OK') {
        Write-Host 'INVALID: the grading harness is incomplete (pytest/json-report unavailable)'
        Write-Host $selfCheck.Trim()
        exit 2
    }

    # ---- the candidate runs inside a write-restricted process ----------------
    # The graded suite has to load the candidate package, so the two share one
    # interpreter. What must not be shared is authority over the verdict: while
    # the suite runs, the scoring directory and every source of the hidden suite
    # deny write access to this account, so the candidate cannot rewrite the
    # checks, the rubric or the suite that judges it. The verdict itself is read
    # from the trusted stdout channel below, never from a file the candidate
    # could have produced.
    $checksDirectory = Split-Path -Parent $ChecksPath
    if (-not (Test-Path -LiteralPath $checksDirectory)) { New-Item -ItemType Directory -Path $checksDirectory -Force | Out-Null }

    $denyTargets = New-Object System.Collections.ArrayList
    foreach ($p in @($checksDirectory, (Join-Path $TaskRoot 'tests'), (Split-Path -Parent $hiddenSuite))) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        if (Test-Path -LiteralPath $p) { [void]$denyTargets.Add((Resolve-Path -LiteralPath $p).Path) }
    }
    $denyTargets = @($denyTargets | Sort-Object -Unique)
    $account = "$env:USERDOMAIN\$env:USERNAME"
    $denyApplied = New-Object System.Collections.ArrayList
    foreach ($p in $denyTargets) {
        & icacls $p /deny "${account}:(W)" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { [void]$denyApplied.Add($p) }
    }

    # The counter-example: inside the restricted window, writing the scoring
    # directory or the hidden-suite sources must be refused. This process is the
    # trusted side and runs as the same account as the candidate, so a refusal
    # here is a refusal for the candidate too.
    $isolationProbes = New-Object System.Collections.ArrayList
    $isolationFailures = New-Object System.Collections.ArrayList
    foreach ($probe in @(
            @{ path = (Join-Path $checksDirectory 'wff-isolation-probe.tmp'); what = 'scoring-directory' },
            @{ path = (Join-Path (Join-Path $TaskRoot 'tests') 'wff-isolation-probe.tmp'); what = 'hidden-suite-source' })) {
        $entry = [ordered]@{ target = $probe.what; path = $probe.path; denied = $false }
        try {
            Set-Content -LiteralPath $probe.path -Value 'probe' -ErrorAction Stop
            Remove-Item -LiteralPath $probe.path -Force -ErrorAction SilentlyContinue
            [void]$isolationFailures.Add("write to $($probe.what) was allowed")
        }
        catch { $entry.denied = $true }
        [void]$isolationProbes.Add([pscustomobject]$entry)
    }
    $isolationEnforced = ($isolationFailures.Count -eq 0 -and $isolationProbes.Count -gt 0)
    Write-Host ("isolation: enforced={0} refused={1}/{2}" -f $isolationEnforced,
        (@($isolationProbes | Where-Object { $_.denied }).Count), $isolationProbes.Count)

    $nonce = [Guid]::NewGuid().ToString('N')
    $env:WFF_GRADING_NONCE = $nonce
    $env:WFF_GRADING_SUITE = Split-Path -Leaf $hiddenSuite
    $env:PYTHONPATH = "$runRoot;$env:PYTHONPATH"
    $pytestText = ''
    try {
        Push-Location -LiteralPath $runRoot
        try {
            $pytestText = (& $python.Source -m pytest -rA --tb=short -p no:cacheprovider --json-report --json-report-file=$reportPath (Join-Path 'tests' 'test_wvas_semantics.py') 2>&1 | Out-String)
        }
        finally {
            Pop-Location
        }
    }
    finally {
        Remove-Item Env:WFF_GRADING_NONCE -ErrorAction SilentlyContinue
        Remove-Item Env:WFF_GRADING_SUITE -ErrorAction SilentlyContinue
        foreach ($p in $denyApplied) { & icacls $p /remove:d $account 2>&1 | Out-Null }
    }
    Write-Host $pytestText

    if (-not (Test-Path -LiteralPath $reportPath)) {
        Write-Host 'INVALID: pytest produced no json report'
        exit 2
    }

    $doc = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json

    # Map the pytest node ids onto the stable contract check ids.
    $slugByFunction = [ordered]@{
        'test_region_addresses_are_64_bit'                      = 'region-addresses-are-64-bit'
        'test_region_sizes_are_64_bit'                          = 'region-sizes-are-64-bit'
        'test_reserved_regions_are_reported'                    = 'reserved-regions-are-reported'
        'test_file_mapping_path_is_a_dos_path'                  = 'file-mapping-path-is-a-dos-path'
        'test_device_paths_are_translated'                      = 'device-paths-are-translated'
        'test_anonymous_mapping_has_no_path'                    = 'anonymous-mapping-has-no-path'
        'test_missing_process_is_classified'                    = 'missing-process-is-classified'
        'test_modules_are_deduplicated'                         = 'modules-are-deduplicated'
        'test_regions_are_sorted_by_base'                       = 'regions-are-sorted-by-base'
        'test_region_records_are_well_formed'                   = 'region-records-are-well-formed'
        'test_own_process_reports_image_regions'                = 'own-process-reports-image-regions'
        'test_file_backed_regions_are_a_subset'                 = 'file-backed-regions-are-a-subset'
        'test_include_reserved_false_only_reports_committed_memory' = 'include-reserved-false-only-reports-committed-memory'
        'test_negative_pid_is_rejected'                         = 'negative-pid-is-rejected'
        'test_modules_are_sorted_by_base'                       = 'modules-are-sorted-by-base'
        'test_visible_smoke_suite_still_passes'                 = 'visible-smoke-suite-still-passes'
    }

    # ---- the trusted channel -------------------------------------------------
    # Per-case outcomes are read from the marker stream the suite mirrors onto
    # pytest's real stdout. That stream is consumed here, by the trusted side, so
    # nothing the candidate writes to disk can rewrite it. The json report is read
    # as well, but only to cross-check the two channels: a disagreement means the
    # verdict was tampered with, and the case is refused instead of being scored.
    $trustedOutcome = @{}
    $trustedSetupFault = @{}
    $marker = '##WFF-OBS##'
    $trustedLines = 0
    foreach ($line in ($pytestText -split "`r?`n")) {
        $idx = $line.IndexOf($marker)
        if ($idx -lt 0) { continue }
        try { $record = ($line.Substring($idx + $marker.Length) | ConvertFrom-Json) }
        catch { continue }
        if ([string]$record.nonce -ne $nonce) { continue }
        $nodeId = [string]$record.nodeid
        if ([string]::IsNullOrWhiteSpace($nodeId)) { continue }
        $fn = ($nodeId -split '::')[-1]
        if (-not $slugByFunction.Contains($fn)) { continue }
        $outcome = ([string]$record.outcome).ToLowerInvariant()
        if ([string]$record.when -ne 'call') {
            # A setup or teardown report: the case never produced a verdict. Keep it
            # as the documented reason the case is missing instead of dropping it.
            if ($outcome -ne 'passed') { $trustedSetupFault[$fn] = "$($record.when):$outcome" }
            continue
        }
        $trustedLines++
        if ($trustedOutcome.ContainsKey($fn)) { $trustedOutcome[$fn] = 'conflict' }
        else { $trustedOutcome[$fn] = $outcome }
    }
    Write-Host ("trusted-channel: {0} case report(s) carried the run nonce" -f $trustedLines)

    $fileOutcome = @{}
    foreach ($test in @($doc.tests)) {
        $nodeId = [string]$test.nodeid
        if ([string]::IsNullOrWhiteSpace($nodeId)) { continue }
        $fn = ($nodeId -split '::')[-1]
        if (-not [string]::IsNullOrWhiteSpace($fn)) { $fileOutcome[$fn] = ([string]$test.outcome).ToLowerInvariant() }
    }

    # Map the trusted outcome onto the contract status. Only a clean pass or a
    # clean failure carries information about the candidate. Anything else -- a
    # fixture setup error, a skip, a teardown error, a missing collection -- means
    # the case was never observed, so it stays INVALID and can never be turned
    # into a candidate score of 0.
    $observed = @{}
    foreach ($fn in @($trustedOutcome.Keys)) {
        $slug = [string]$slugByFunction[$fn]
        $outcome = [string]$trustedOutcome[$fn]
        if ($outcome -eq 'conflict') { $status = 'INVALID' }
        elseif ($outcome -eq 'passed' -or $outcome -eq 'xpassed') { $status = 'PASS' }
        elseif ($outcome -eq 'failed' -or $outcome -eq 'xfailed') { $status = 'FAIL' }
        else { $status = 'INVALID' }
        $detail = "trusted outcome=$outcome"
        if ($fileOutcome.ContainsKey($fn) -and [string]$fileOutcome[$fn] -ne $outcome) {
            $status = 'INVALID'
            $detail = "trusted outcome=$outcome but the on-disk report says $($fileOutcome[$fn])"
        }
        $observed[$slug] = @{ Status = $status; Detail = $detail }
    }

    # A run whose confinement could not be established is not evidence of anything.
    # The reviewer contract requires the candidate to be confined, so an unconfined
    # run is refused in full instead of being scored.
    if (-not $isolationEnforced) {
        $observed = @{}
        Write-Host 'INVALID: the candidate could not be confined to a write-restricted process'
    }

    $results = New-Object System.Collections.ArrayList
    foreach ($entry in $slugByFunction.GetEnumerator()) {
        $slug = [string]$entry.Value
        if ($observed.ContainsKey($slug)) {
            $state = $observed[$slug]
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = $state.Status; detail = $state.Detail })
        }
        else {
            # A required check the suite never reported is missing evidence, not a
            # candidate failure. An empty collection is a harness fault as much as
            # a dependency failure is, so it can never be scored as a legitimate 0.
            $detail = 'required check was not collected'
            if ($trustedLines -eq 0) { $detail = 'the suite collected no case at all' }
            if (-not $isolationEnforced) { $detail = 'the candidate could not be confined to a write-restricted process' }
            if ($trustedSetupFault.ContainsKey($entry.Key)) { $detail = "the case never ran ($($trustedSetupFault[$entry.Key]))" }
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = 'INVALID'; detail = $detail })
        }
    }

    $payload = [pscustomobject][ordered]@{
        task_id      = 'wfflab__wvas-216'
        task_version = '1.0.1'
        checks       = @($results.ToArray())
        isolation    = [pscustomobject][ordered]@{
            enforced      = $isolationEnforced
            restricted    = @($denyApplied.ToArray())
            probes        = @($isolationProbes.ToArray())
            failures      = @($isolationFailures.ToArray())
            trusted_cases = $trustedLines
        }
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ChecksPath -Encoding UTF8

    $failed = @($results | Where-Object { $_.status -eq 'FAIL' }).Count
    $invalid = @($results | Where-Object { $_.status -eq 'INVALID' }).Count
    Write-Host ("checks: {0} passed, {1} failed, {2} invalid, {3} total" -f ($results.Count - $failed - $invalid), $failed, $invalid, $results.Count)

    if ($invalid -gt 0) {
        Write-Host ("INVALID: {0} required check(s) were not observed; incomplete evidence is never a candidate score" -f $invalid)
        exit 2
    }
    if ($failed -gt 0) { exit 1 }
    exit 0
}
finally {
    foreach ($p in @($denyApplied)) { if ($p) { & icacls $p /remove:d $account 2>&1 | Out-Null } }
    if (Test-Path -LiteralPath $runRoot) { Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
