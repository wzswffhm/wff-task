# Generated for wfflab__wpeimg-219 by the task authoring pipeline.
#
# Objective checks for the wpeimg container-format behaviour contract. The hidden
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
    foreach ($relative in @('tests\test_wpeimg_semantics.py', 'test_wpeimg_semantics.py')) {
        $candidate = Join-Path $Root $relative
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return ''
}

$verifierCandidates = New-Object System.Collections.ArrayList
if (-not [string]::IsNullOrWhiteSpace($VerifierRoot)) { [void]$verifierCandidates.Add($VerifierRoot) }
if (-not [string]::IsNullOrWhiteSpace($env:WPEIMG_VERIFIER_ROOT)) { [void]$verifierCandidates.Add($env:WPEIMG_VERIFIER_ROOT) }
# Resolution order. The verifier-side injection point comes first; C:\tests is
# the platform's own copy channel (Harbor copies the package's tests/ directory
# to C:\tests right before it runs tests/test.ps1, which is the only way the
# suite reaches a container that never mounts verifier/). The sibling
# outside_harbor-verifier/ directory is the local-reproduction fallback used by
# the task authoring pipeline; it is never mounted into the task root.
#
# The workspace is deliberately absent from this list: a candidate must never be
# able to supply the grading assertions.
[void]$verifierCandidates.Add('C:\verifier\wfflab__wpeimg-219')
[void]$verifierCandidates.Add('C:\verifier')
[void]$verifierCandidates.Add('C:\tests')
$packageRoot = Split-Path -Parent $TaskRoot
if (-not [string]::IsNullOrWhiteSpace($packageRoot)) {
    [void]$verifierCandidates.Add((Join-Path $packageRoot 'outside_harbor-verifier\wfflab__wpeimg-219'))
}

$hiddenSuite = ''
foreach ($candidate in $verifierCandidates) {
    $hiddenSuite = Resolve-HiddenSuite $candidate
    if (-not [string]::IsNullOrWhiteSpace($hiddenSuite)) { break }
}

# ---- infrastructure preconditions -----------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $WorkspaceRoot 'wpeimg') '__init__.py'))) {
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
$runRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('wpeimg-graded-' + [Guid]::NewGuid().ToString('N'))
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
    Copy-Item -LiteralPath $hiddenSuite -Destination (Join-Path $testsDir 'test_wpeimg_semantics.py') -Force

    # The suite may import verifier-side helper modules that sit next to it
    # (for example win_services.py, which wraps imagehlp/kernel32). They are
    # part of the graded material and must land in the scratch tests/ directory
    # too, otherwise the container run dies with ModuleNotFoundError even though
    # the same suite passes locally.
    # NOTE: use [System.IO.Path] here — `Split-Path -LiteralPath X -Parent`
    # cannot resolve its parameter set and would silently leave the directory
    # empty, which is exactly how the helpers went missing before.
    $suiteDir = [System.IO.Path]::GetDirectoryName($hiddenSuite)
    $hiddenLeaf = [System.IO.Path]::GetFileName($hiddenSuite)
    if (-not $suiteDir) {
        Write-Host "INVALID: cannot resolve the hidden suite directory from $hiddenSuite"
        exit 2
    }
    Get-ChildItem -LiteralPath $suiteDir -Filter '*.py' -File |
        Where-Object { $_.Name -ne $hiddenLeaf } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $testsDir $_.Name) -Force
        }

    # The embed interpreter isolates sys.path through python312._pth, so PYTHONPATH
    # alone is not enough. Drop a conftest that prepends the scratch root so that
    # `import wpeimg` resolves against the staged candidate package.
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
        & $python.Source -m pytest -rA --tb=short -p no:cacheprovider --json-report --json-report-file=$reportPath (Join-Path 'tests' 'test_wpeimg_semantics.py') 2>&1 | Out-Host
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
        'test_amd64_sample_inspects'                       = 'amd64-sample-inspects'
        'test_i386_sample_inspects'                        = 'i386-sample-inspects'
        'test_data_directories_follow_the_pe_order'        = 'data-directories-follow-the-pe-order'
        'test_data_directories_use_the_layout_specific_offset' = 'data-directories-use-the-layout-specific-offset'
        'test_data_directories_respect_declared_count'     = 'data-directories-respect-declared-count'
        'test_data_directories_ignore_slots_the_header_cannot_hold' = 'data-directories-ignore-slots-the-header-cannot-hold'
        'test_authenticode_signature_detection'            = 'authenticode-signature-detection'
        'test_authenticode_signature_requires_backing_bytes' = 'authenticode-signature-requires-backing-bytes'
        'test_trailing_bytes_are_not_a_structural_error'   = 'trailing-bytes-are-not-a-structural-error'
        'test_signature_info_describes_the_real_signed_data' = 'signature-info-describes-the-real-signed-data'
        'test_signature_info_without_a_certificate_table'  = 'signature-info-without-a-certificate-table'
        'test_signature_info_skips_non_pkcs7_records'      = 'signature-info-skips-non-pkcs7-records'
        'test_signature_info_rejects_a_length_that_cannot_hold' = 'signature-info-rejects-a-length-that-cannot-hold'
        'test_signature_info_is_offline_and_standard_library_only' = 'signature-info-is-offline-and-standard-library-only'
        'test_checksum_matches_a_live_windows_query'       = 'checksum-matches-a-live-windows-query'
        'test_checksum_matches_live_queries_across_variants' = 'checksum-matches-live-queries-across-variants'
        'test_iter_sections_reads_a_real_windows_file_handle' = 'iter-sections-reads-a-real-windows-file-handle'
        'test_iter_sections_is_bounded_on_a_real_handle'   = 'iter-sections-is-bounded-on-a-real-handle'
        'test_checksum_matches_authoritative_values'       = 'checksum-matches-authoritative-values'
        'test_checksum_ignores_the_stored_field'           = 'checksum-ignores-the-stored-field'
        'test_accumulator_matches_authoritative_values'    = 'accumulator-matches-authoritative-values'
        'test_rva_inside_headers_maps_to_itself'           = 'rva-inside-headers-maps-to-itself'
        'test_rva_inside_a_section_maps_into_the_file'     = 'rva-inside-a-section-maps-into-the-file'
        'test_rva_in_an_uninitialised_tail_has_no_backing' = 'rva-in-an-uninitialised-tail-has-no-backing'
        'test_rva_outside_every_section_has_no_backing'    = 'rva-outside-every-section-has-no-backing'
        'test_truncated_section_table_reports_truncated'   = 'truncated-section-table-reports-truncated'
        'test_unknown_optional_magic_reports_optional'     = 'unknown-optional-magic-reports-optional'
        'test_section_past_end_of_file_reports_structure'  = 'section-past-end-of-file-reports-structure'
        'test_overlapping_virtual_sections_reports_structure' = 'overlapping-virtual-sections-reports-structure'
        'test_overlapping_file_ranges_reports_structure'   = 'overlapping-file-ranges-reports-structure'
        'test_unaligned_section_reports_structure'         = 'unaligned-section-reports-structure'
        'test_undersized_size_of_image_reports_structure'  = 'undersized-size-of-image-reports-structure'
        'test_structure_is_reported_before_checksum'       = 'structure-is-reported-before-checksum'
        'test_iter_sections_does_not_slurp_the_stream'     = 'iter-sections-does-not-slurp-the-stream'
        'test_verify_rejects_every_structural_variant'     = 'verify-rejects-every-structural-variant'
        'test_non_mz_prefix_reports_dos'                   = 'non-mz-prefix-reports-dos'
        'test_missing_pe_signature_reports_signature'      = 'missing-pe-signature-reports-signature'
        'test_mismatched_checksum_reports_checksum'        = 'mismatched-checksum-reports-checksum'
        'test_verify_never_raises'                         = 'verify-never-raises'
        'test_negative_rva_has_no_backing'                 = 'negative-rva-has-no-backing'
        'test_public_surface_is_unchanged'                 = 'public-surface-is-unchanged'
        'test_accumulator_matches_one_shot_helper'         = 'accumulator-matches-one-shot-helper'
        'test_package_has_no_external_dependencies'        = 'package-has-no-external-dependencies'
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
        task_id      = 'wfflab__wpeimg-219'
        task_version = '1.4.0'
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
