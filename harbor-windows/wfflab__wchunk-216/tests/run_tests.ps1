# Generated for wfflab__wchunk-216 by the task authoring pipeline. Do not edit by hand.
#
# Objective checks for the wchunk container-format behaviour contract. The hidden
# semantic suite is executed against the candidate package with pytest and its
# per-test outcome is mapped onto stable check ids. Scoring is delegated to
# aggregate_results.ps1.
#
# Exit codes:
#   0  every check passed
#   1  at least one check failed (functional failure)
#   2  the harness itself could not run (infrastructure failure)

[CmdletBinding()]
param(
    [string]$WorkspaceRoot = '',
    [string]$ChecksPath = '',
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { $WorkspaceRoot = Join-Path $TaskRoot 'environment\workspace' }
if ([string]::IsNullOrWhiteSpace($ChecksPath)) { $ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json') }

$hiddenSuite = Join-Path $TaskRoot 'tests\hidden\test_wchunk_semantics.py'

# ---- infrastructure preconditions -----------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $WorkspaceRoot 'wchunk') '__init__.py'))) {
    Write-Host "INVALID: candidate package not found under $WorkspaceRoot"
    exit 2
}
if (-not (Test-Path -LiteralPath $hiddenSuite)) {
    Write-Host "INVALID: hidden semantic suite not found at $hiddenSuite"
    exit 2
}

# The graded suite runs against a scratch copy so that pytest artefacts never
# touch the (possibly read-only) workspace and so a stale cache cannot leak in.
$runRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('wchunk-graded-' + [Guid]::NewGuid().ToString('N'))
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
    Copy-Item -LiteralPath $hiddenSuite -Destination (Join-Path $testsDir 'test_wchunk_semantics.py') -Force

    # The embed interpreter isolates sys.path through python312._pth, so PYTHONPATH
    # alone is not enough. Drop a conftest that prepends the scratch root so that
    # `import wchunk` resolves against the staged candidate package.
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
        & $python.Source -m pytest -rA --tb=short -p no:cacheprovider --json-report --json-report-file=$reportPath (Join-Path 'tests' 'test_wchunk_semantics.py') 2>&1 | Out-Host
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
        'test_sample_verifies'                      = 'sample-verifies'
        'test_sample_roundtrip_byte_identical'      = 'sample-roundtrip-byte-identical'
        'test_sample_records_match_expected'        = 'sample-records-match-expected'
        'test_empty_sample_roundtrip'               = 'empty-sample-roundtrip'
        'test_record_alignment_is_eight_bytes'      = 'record-alignment-is-eight-bytes'
        'test_crc_matches_standard_check_value'     = 'crc-matches-standard-check-value'
        'test_tampered_content_is_rejected'         = 'tampered-content-is-rejected'
        'test_checksum_covers_header_and_records'   = 'checksum-covers-header-and-records'
        'test_truncated_container_reports_truncated'= 'truncated-container-reports-truncated'
        'test_truncated_stream_reports_truncated'   = 'truncated-stream-reports-truncated'
        'test_bad_magic_reports_magic'              = 'bad-magic-reports-magic'
        'test_bad_version_reports_version'          = 'bad-version-reports-version'
        'test_verify_never_raises'                  = 'verify-never-raises'
        'test_iter_records_is_streaming'            = 'iter-records-is-streaming'
        'test_self_roundtrip_small_records'         = 'self-roundtrip-small-records'
        'test_empty_payload_roundtrip'              = 'empty-payload-roundtrip'
        'test_generated_data_roundtrip_verified'    = 'generated-data-roundtrip-verified'
        'test_read_all_matches_unpack'              = 'read-all-matches-unpack'
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
            # A required check that the suite never reported is a failure of the
            # candidate contract (missing collection), not an infrastructure fault.
            [void]$results.Add([pscustomobject][ordered]@{ test_id = $slug; status = 'FAIL'; detail = 'required check was not collected' })
        }
    }

    $checksDirectory = Split-Path -Parent $ChecksPath
    if (-not (Test-Path -LiteralPath $checksDirectory)) { New-Item -ItemType Directory -Path $checksDirectory -Force | Out-Null }

    $payload = [pscustomobject][ordered]@{
        task_id      = 'wfflab__wchunk-216'
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
