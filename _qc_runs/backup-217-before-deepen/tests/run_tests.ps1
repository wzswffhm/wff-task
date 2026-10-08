# Generated for wfflab__wreparse-217. Do not edit by hand.
#
# Objective checks for the WReparse behaviour contract. Writes a machine
# readable checks file; scoring is delegated to aggregate_results.ps1.
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

# prepare.ps1 builds the fixture on the container's writable layer, outside the
# task tree, because bind-mounted task trees cannot host hard links or symbolic
# links. The manifest location here must stay in step with that script.
$fixtureManifest = Join-Path (Join-Path $env:SystemDrive 'wreparse-fixture') ('fixture' + '.json')
$modulePath = Join-Path (Join-Path $WorkspaceRoot 'WReparse') ('WReparse' + '.psd1')

# ---- infrastructure preconditions -----------------------------------------
if (-not (Test-Path -LiteralPath $modulePath)) {
    Write-Host "INVALID: candidate module not found at $modulePath"
    exit 2
}
if (-not (Test-Path -LiteralPath $fixtureManifest)) {
    Write-Host "INVALID: fixture manifest not found at $fixtureManifest; prepare.ps1 did not run"
    exit 2
}

$fixture = Get-Content -LiteralPath $fixtureManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$scanRoot = [string]$fixture.ScanRoot
$fixtureBase = [string]$fixture.Base

try {
    Import-Module $modulePath -Force -ErrorAction Stop
}
catch {
    Write-Host "INVALID: importing the candidate module failed: $($_.Exception.Message)"
    exit 2
}

$results = New-Object System.Collections.ArrayList

function Get-WReparseTestRecord {
    param($Report, [string]$RelativePath)
    if ($null -eq $Report) { return $null }
    foreach ($record in @($Report.Records)) {
        if ([string]::Equals([string]$record.RelativePath, $RelativePath, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $record
        }
    }
    return $null
}

function Test-WReparseHasError {
    param($Report, [string]$Code)
    if ($null -eq $Report) { return $false }
    foreach ($error in @($Report.Errors)) {
        if ([string]$error.Code -eq $Code) { return $true }
    }
    return $false
}

function Add-WReparseCheck {
    param([string]$TestId, [scriptblock]$Body)
    $status = 'FAIL'
    $detail = ''
    try {
        $outcome = & $Body
        if ($outcome -eq $true) { $status = 'PASS' }
        elseif ($outcome -is [string] -and $outcome.Length -gt 0) { $detail = $outcome }
        else { $detail = 'assertion evaluated to false' }
    }
    catch {
        $detail = "exception: $($_.Exception.Message)"
    }
    [void]$results.Add([pscustomobject][ordered]@{ test_id = $TestId; status = $status; detail = $detail })
    if ($detail) { Write-Host ("[{0}] {1} -- {2}" -f $status, $TestId, $detail) }
    else { Write-Host ("[{0}] {1}" -f $status, $TestId) }
}

# Deterministic working directory so that any implementation resolving a
# relative link target against the process CWD is observable.
Set-Location -LiteralPath $TaskRoot

$reportError = $null
$never = $null
$follow = $null
try {
    $never = Get-WReparseReport -Root $scanRoot
    $follow = Get-WReparseReport -Root $scanRoot -Follow
}
catch {
    $reportError = "Get-WReparseReport threw: $($_.Exception.Message)"
    Write-Host "NOTE: $reportError"
}

# ---- required behaviour ----------------------------------------------------
Add-WReparseCheck 'inscope-uses-directory-boundary' {
    if ($reportError) { return $reportError }
    $prefixed = Get-WReparseTestRecord -Report $never -RelativePath 'link-prefix'
    $inside = Get-WReparseTestRecord -Report $never -RelativePath 'link-in'
    if ($null -eq $prefixed) { return 'record link-prefix is missing' }
    if ($prefixed.InScope -ne $false) { return 'link-prefix was reported InScope; its target only shares a name prefix with the scan root' }
    if ($null -eq $inside) { return 'record link-in is missing' }
    if ($inside.InScope -ne $true) { return 'link-in was reported out of scope; its target is inside the scan root' }
    return $true
}

Add-WReparseCheck 'relative-target-resolves-against-link-directory' {
    if ($reportError) { return $reportError }
    $relative = Get-WReparseTestRecord -Report $never -RelativePath 'link-rel'
    if ($null -eq $relative) { return 'record link-rel is missing' }
    $expected = Join-Path $scanRoot 'docs'
    if (([string]$relative.ResolvedTarget) -ne $expected) {
        return "link-rel ResolvedTarget was '$($relative.ResolvedTarget)', expected '$expected'"
    }
    return $true
}

Add-WReparseCheck 'canonical-path-preserves-case' {
    $probe = Join-Path ($env:SystemDrive + '\WReparseCaseProbe') 'Sub'
    $actual = [string](Get-WReparseCanonicalPath -Path $probe)
    if ($actual -cne $probe) { return "Get-WReparseCanonicalPath('$probe') returned '$actual'" }
    return $true
}

Add-WReparseCheck 'hardlink-is-not-a-reparse-point' {
    if ($reportError) { return $reportError }
    $hardlink = Get-WReparseTestRecord -Report $never -RelativePath 'hardlink.txt'
    if ($null -eq $hardlink) { return 'record hardlink.txt is missing' }
    if ([string]$hardlink.Kind -ne 'File') {
        return "hardlink.txt Kind was '$($hardlink.Kind)'; a hard link carries no reparse attribute and must be a File"
    }
    return $true
}

Add-WReparseCheck 'default-scan-does-not-follow-reparse-points' {
    if ($reportError) { return $reportError }
    if ([int]$never.Stats.Skipped -ne 6) {
        return "Stats.Skipped was $($never.Stats.Skipped); the default scan must not enter any of the 6 reparse points"
    }
    return $true
}

Add-WReparseCheck 'depth-starts-at-one' {
    if ($reportError) { return $reportError }
    $plain = Get-WReparseTestRecord -Report $never -RelativePath 'plain.txt'
    if ($null -eq $plain) { return 'record plain.txt is missing' }
    if ([int]$plain.Depth -ne 1) { return "plain.txt Depth was $($plain.Depth), expected 1" }
    return $true
}

Add-WReparseCheck 'reparse-kind-distinguishes-junction-and-symbolic-link' {
    if ($reportError) { return $reportError }
    $junction = Get-WReparseTestRecord -Report $never -RelativePath 'link-in'
    $symbolic = Get-WReparseTestRecord -Report $never -RelativePath 'link-rel'
    if ($null -eq $junction -or $null -eq $symbolic) { return 'link-in or link-rel record is missing' }
    if ([string]$junction.ReparseKind -ne 'Junction') {
        return "link-in ReparseKind was '$($junction.ReparseKind)', expected 'Junction'"
    }
    if ([string]$symbolic.ReparseKind -ne 'SymbolicLink') {
        return "link-rel ReparseKind was '$($symbolic.ReparseKind)', expected 'SymbolicLink'"
    }
    return $true
}

Add-WReparseCheck 'records-are-sorted-by-contract-order' {
    if ($reportError) { return $reportError }
    $paths = @($never.Records | ForEach-Object { [string]$_.RelativePath })
    for ($index = 0; $index -lt $paths.Count - 1; $index++) {
        $comparison = [System.StringComparer]::OrdinalIgnoreCase.Compare($paths[$index], $paths[$index + 1])
        if ($comparison -eq 0) { $comparison = [System.StringComparer]::Ordinal.Compare($paths[$index], $paths[$index + 1]) }
        if ($comparison -gt 0) {
            return "records are out of contract order: '$($paths[$index])' precedes '$($paths[$index + 1])'"
        }
    }
    return $true
}

Add-WReparseCheck 'stats-count-reparse-points-separately' {
    if ($reportError) { return $reportError }
    $directories = @($never.Records | Where-Object { [string]$_.Kind -eq 'Directory' }).Count
    $files = @($never.Records | Where-Object { [string]$_.Kind -eq 'File' }).Count
    $reparse = @($never.Records | Where-Object { [string]$_.Kind -eq 'ReparsePoint' }).Count
    if ([int]$never.Stats.Directories -ne $directories) {
        return "Stats.Directories was $($never.Stats.Directories) but $directories records are Directory"
    }
    if ([int]$never.Stats.Files -ne $files) {
        return "Stats.Files was $($never.Stats.Files) but $files records are File"
    }
    if ([int]$never.Stats.ReparsePoints -ne $reparse) {
        return "Stats.ReparsePoints was $($never.Stats.ReparsePoints) but $reparse records are ReparsePoint"
    }
    return $true
}

Add-WReparseCheck 'report-is-byte-identical-across-runs' {
    if ($reportError) { return $reportError }
    $first = ConvertTo-WReparseJson -Report (Get-WReparseReport -Root $scanRoot)
    Start-Sleep -Milliseconds 25
    $second = ConvertTo-WReparseJson -Report (Get-WReparseReport -Root $scanRoot)
    if ($first -cne $second) { return 'two consecutive reports of the same tree differ; the report must not embed volatile values' }
    return $true
}

# ---- contract clauses declared in REPARSE-CONTRACT.md and now enforced -------
# Each of these restates a rule that the behaviour contract already makes
# authoritative: no new requirement is introduced here.
Add-WReparseCheck 'canonical-path-keeps-volume-root' {
    $volumeRoot = $env:SystemDrive + '\'
    $actual = [string](Get-WReparseCanonicalPath -Path $volumeRoot)
    if ($actual -cne $volumeRoot) {
        return "Get-WReparseCanonicalPath('$volumeRoot') returned '$actual'; a volume root keeps its trailing separator"
    }
    return $true
}

Add-WReparseCheck 'canonical-path-strips-trailing-separator' {
    $probe = (Join-Path ($env:SystemDrive + '\WReparseTrail') 'Sub') + '\'
    $expected = Join-Path ($env:SystemDrive + '\WReparseTrail') 'Sub'
    $actual = [string](Get-WReparseCanonicalPath -Path $probe)
    if ($actual -cne $expected) {
        return "Get-WReparseCanonicalPath('$probe') returned '$actual', expected '$expected'"
    }
    return $true
}

Add-WReparseCheck 'within-root-includes-the-root-itself' {
    $inside = Test-WReparseWithinRoot -Path $scanRoot -Root $scanRoot
    if ($inside -ne $true) {
        return "Test-WReparseWithinRoot returned '$inside' for the root itself; a path equal to the root is inside"
    }
    return $true
}

Add-WReparseCheck 'reparse-records-use-contract-depth' {
    if ($reportError) { return $reportError }
    $link = Get-WReparseTestRecord -Report $never -RelativePath 'link-in'
    if ($null -eq $link) { return 'record link-in is missing' }
    if ([int]$link.Depth -ne 1) {
        return "link-in Depth was $($link.Depth), expected 1 (a direct child of the scan root)"
    }
    return $true
}

Add-WReparseCheck 'non-file-records-report-zero-size' {
    if ($reportError) { return $reportError }
    $directory = Get-WReparseTestRecord -Report $never -RelativePath 'docs'
    $link = Get-WReparseTestRecord -Report $never -RelativePath 'link-in'
    if ($null -eq $directory -or $null -eq $link) { return 'docs or link-in record is missing' }
    if ([long]$directory.Size -ne 0) { return "docs Size was $($directory.Size); a directory reports 0" }
    if ([long]$link.Size -ne 0) { return "link-in Size was $($link.Size); a reparse entry reports 0" }
    return $true
}

Add-WReparseCheck 'reparse-target-is-recorded-verbatim' {
    if ($reportError) { return $reportError }
    $link = Get-WReparseTestRecord -Report $never -RelativePath 'link-rel'
    if ($null -eq $link) { return 'record link-rel is missing' }
    if ([string]$link.Target -ne 'docs') {
        return "link-rel Target was '$($link.Target)'; the raw on-disk target string must be recorded verbatim"
    }
    return $true
}

Add-WReparseCheck 'depth-limit-reports-too-deep' {
    $shallow = Get-WReparseReport -Root $scanRoot -MaxDepth 1
    if (-not (Test-WReparseHasError -Report $shallow -Code 'too_deep')) {
        return "no 'too_deep' error was reported when MaxDepth is 1"
    }
    return $true
}

Add-WReparseCheck 'error-list-is-stably-sorted' {
    if ($reportError) { return $reportError }
    $errors = @($follow.Errors)
    for ($index = 0; $index -lt $errors.Count - 1; $index++) {
        $left = [string]$errors[$index].RelativePath + [string][char]0 + [string]$errors[$index].Code
        $right = [string]$errors[$index + 1].RelativePath + [string][char]0 + [string]$errors[$index + 1].Code
        $comparison = [System.StringComparer]::OrdinalIgnoreCase.Compare($left, $right)
        if ($comparison -eq 0) { $comparison = [System.StringComparer]::Ordinal.Compare($left, $right) }
        if ($comparison -gt 0) { return "errors are out of contract order at index $index" }
    }
    return $true
}

# ---- regressions the current code already satisfies -------------------------
Add-WReparseCheck 'schema-version-is-reported' {
    if ($reportError) { return $reportError }
    if ([string]$never.SchemaVersion -ne ('wreparse' + '/1.0')) { return "SchemaVersion was '$($never.SchemaVersion)'" }
    return $true
}

Add-WReparseCheck 'plain-entries-are-enumerated' {
    if ($reportError) { return $reportError }
    $expectations = @(
        @{ Path = 'plain.txt'; Kind = 'File' },
        @{ Path = 'docs'; Kind = 'Directory' },
        @{ Path = (Join-Path (Join-Path 'docs' 'nested') 'deep.txt'); Kind = 'File' },
        @{ Path = (Join-Path 'beta' 'zeta.txt'); Kind = 'File' }
    )
    foreach ($expectation in $expectations) {
        $record = Get-WReparseTestRecord -Report $never -RelativePath $expectation.Path
        if ($null -eq $record) { return "record $($expectation.Path) is missing" }
        if ([string]$record.Kind -ne $expectation.Kind) {
            return "$($expectation.Path) Kind was '$($record.Kind)', expected '$($expectation.Kind)'"
        }
    }
    return $true
}

Add-WReparseCheck 'nonexistent-root-reports-not-found' {
    $missing = Join-Path $fixtureBase 'no-such-directory'
    $report = Get-WReparseReport -Root $missing
    if (-not (Test-WReparseHasError -Report $report -Code 'not_found')) { return "no 'not_found' error was reported for a missing scan root" }
    return $true
}

Add-WReparseCheck 'file-root-reports-structure' {
    $fileRoot = Join-Path $scanRoot 'plain.txt'
    $report = Get-WReparseReport -Root $fileRoot
    if (-not (Test-WReparseHasError -Report $report -Code 'structure')) { return "no 'structure' error was reported when the scan root is a file" }
    return $true
}

Add-WReparseCheck 'cycle-is-reported-when-following' {
    if ($reportError) { return $reportError }
    if (-not (Test-WReparseHasError -Report $follow -Code 'cycle')) { return "no 'cycle' error was reported in follow mode" }
    return $true
}

Add-WReparseCheck 'broken-target-is-reported-when-following' {
    if ($reportError) { return $reportError }
    if (-not (Test-WReparseHasError -Report $follow -Code 'broken_target')) { return "no 'broken_target' error was reported in follow mode" }
    return $true
}

# ---- persist ---------------------------------------------------------------
$checksDirectory = Split-Path -Parent $ChecksPath
if (-not (Test-Path -LiteralPath $checksDirectory)) { New-Item -ItemType Directory -Path $checksDirectory -Force | Out-Null }

$payload = [pscustomobject][ordered]@{
    task_id      = 'wfflab__wreparse-217'
    task_version = '1.0.0'
    scan_root    = $scanRoot
    checks       = @($results.ToArray())
}
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ChecksPath -Encoding UTF8

$failed = @($results | Where-Object { $_.status -ne 'PASS' }).Count
Write-Host ("checks: {0} passed, {1} failed, {2} total" -f ($results.Count - $failed), $failed, $results.Count)

if ($failed -gt 0) { exit 1 }
exit 0
