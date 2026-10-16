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
    # `import wvas` resolves against the staged candidate package.
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
        & $python.Source -m pytest -rA --tb=short -p no:cacheprovider --json-report --json-report-file=$reportPath (Join-Path 'tests' 'test_wvas_semantics.py') 2>&1 | Out-Host
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

    $observed = @{}
    foreach ($test in @($doc.tests)) {
        $nodeId = [string]$test.nodeid
        if ([string]::IsNullOrWhiteSpace($nodeId)) { continue }
        $function = ($nodeId -split '::')[-1]
        if (-not $slugByFunction.Contains($function)) { continue }
        $slug = [string]$slugByFunction[$function]
        $outcome = ([string]$test.outcome).ToLowerInvariant()
        $status = if ($outcome -eq 'passed' -or $outcome -eq 'xpassed') { 'PASS' } else { 'FAIL' }
        $observed[$slug] = @{ Status = $status; Detail = "pytest outcome=$outcome" }
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
            # candidate failure. aggregate_results.ps1 turns any status other than
            # PASS or FAIL into run_validity=INVALID, so a missing collection can
            # never be scored as a legitimate 0.
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = 'INVALID'; detail = 'required check was not collected' })
        }
    }

    $checksDirectory = Split-Path -Parent $ChecksPath
    if (-not (Test-Path -LiteralPath $checksDirectory)) { New-Item -ItemType Directory -Path $checksDirectory -Force | Out-Null }

    $payload = [pscustomobject][ordered]@{
        task_id      = 'wfflab__wvas-216'
        task_version = '1.0.0'
        checks       = @($results.ToArray())
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ChecksPath -Encoding UTF8

    $failed = @($results | Where-Object { $_.status -ne 'PASS' }).Count
    Write-Host ("checks: {0} passed, {1} failed, {2} total" -f ($results.Count - $failed), $failed, $results.Count)

    if ($failed -gt 0) { exit 1 }
    exit 0
}
finally {
    if (Test-Path -LiteralPath $runRoot) { Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
