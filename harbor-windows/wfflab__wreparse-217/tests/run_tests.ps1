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
    if ([int]$never.Stats.Skipped -ne 8) {
        return "Stats.Skipped was $($never.Stats.Skipped); the default scan must not enter any of the 8 reparse points"
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

# ---- deepening round 1.1.0: contract clauses previously not covered ---------

Add-WReparseCheck 'negative-maxdepth-is-treated-as-zero' {
    $negative = Get-WReparseReport -Root $scanRoot -MaxDepth -5
    $zero = Get-WReparseReport -Root $scanRoot -MaxDepth 0
    if ((ConvertTo-WReparseJson -Report $negative) -ne (ConvertTo-WReparseJson -Report $zero)) {
        return 'a negative -MaxDepth must behave exactly like 0'
    }
    if (-not (Test-WReparseHasError -Report $negative -Code 'too_deep')) {
        return "no 'too_deep' error was reported for -MaxDepth < 0"
    }
    return $true
}

Add-WReparseCheck 'invalid-root-reports-invalid-argument' {
    $report = Get-WReparseReport -Root 'C:\bad<name>|x'
    if (-not (Test-WReparseHasError -Report $report -Code 'invalid_argument')) {
        return "no 'invalid_argument' error was reported for a root that cannot be normalised"
    }
    return $true
}

Add-WReparseCheck 'follow-uses-link-path-prefix' {
    if ($reportError) { return $reportError }
    $viaLink = Get-WReparseTestRecord -Report $follow -RelativePath (Join-Path 'link-in' 'readme.txt')
    if ($null -eq $viaLink) {
        return 'in follow mode, entries reached through a link must be named with the link path prefix'
    }
    if ([string]$viaLink.Kind -ne 'File') { return "the entry reached through link-in had Kind '$($viaLink.Kind)'" }
    return $true
}

Add-WReparseCheck 'follow-file-link-produces-no-children' {
    if ($reportError) { return $reportError }
    $link = Get-WReparseTestRecord -Report $follow -RelativePath 'link-file'
    if ($null -eq $link) { return 'record link-file is missing in follow mode' }
    $children = @($follow.Records | Where-Object { ([string]$_.RelativePath) -like 'link-file\*' })
    if ($children.Count -ne 0) {
        return "a link whose target is a file must not produce child entries, found $($children.Count)"
    }
    return $true
}

Add-WReparseCheck 'repeated-target-in-sibling-branch-is-not-a-cycle' {
    if ($reportError) { return $reportError }
    $twin = Get-WReparseTestRecord -Report $follow -RelativePath 'link-twin'
    if ($null -eq $twin) { return 'record link-twin is missing in follow mode' }
    $cycleForTwin = @($follow.Errors | Where-Object { [string]$_.Code -eq 'cycle' -and [string]$_.RelativePath -eq 'link-twin' })
    if ($cycleForTwin.Count -gt 0) {
        return 'a target already visited in a sibling branch is not an ancestor cycle'
    }
    $child = Get-WReparseTestRecord -Report $follow -RelativePath (Join-Path 'link-twin' 'readme.txt')
    if ($null -eq $child) { return 'link-twin must be entered: its target is not on the current ancestry chain' }
    return $true
}

Add-WReparseCheck 'empty-tree-serialises-empty-arrays' {
    $report = Get-WReparseReport -Root (Join-Path $scanRoot 'empty')
    $json = ConvertTo-WReparseJson -Report $report
    if ($json -notmatch '"Records"\s*:\s*\[\s*\]') { return 'an empty Records collection must serialise as []' }
    if ($json -notmatch '"Errors"\s*:\s*\[\s*\]') { return 'an empty Errors collection must serialise as []' }
    return $true
}

# ---- deepening round 1.3.0: contract clauses previously not covered ---------
# Each check restates a rule the behaviour contract already makes authoritative;
# no new requirement is introduced.

Add-WReparseCheck 'sorting-is-culture-independent' {
    if ($reportError) { return $reportError }
    $asciiZ = [string][char]0x005A + '.txt'
    $umlautA = [string][char]0x00C4 + '.txt'
    $umlautO = [string][char]0x00F6 + '.txt'
    $paths = @($never.Records | ForEach-Object { [string]$_.RelativePath })
    $indexOf = @{}
    for ($i = 0; $i -lt $paths.Count; $i++) { if (-not $indexOf.ContainsKey($paths[$i])) { $indexOf[$paths[$i]] = $i } }
    foreach ($name in @($asciiZ, $umlautA, $umlautO)) {
        if (-not $indexOf.ContainsKey($name)) { return "record '$name' is missing from the report" }
    }
    if ($indexOf[$asciiZ] -ge $indexOf[$umlautA] -or $indexOf[$umlautA] -ge $indexOf[$umlautO]) {
        return ("records are not in ordinal order around the non-ASCII names " +
                "($asciiZ at $($indexOf[$asciiZ]), $umlautA at $($indexOf[$umlautA]), $umlautO at $($indexOf[$umlautO])); " +
                "the contract requires an ordinal-ignore-case key, so a culture-aware sort is not acceptable")
    }
    return $true
}

Add-WReparseCheck 'module-exports-exactly-six-functions' {
    $expected = @(
        'Get-WReparseReport', 'ConvertTo-WReparseJson', 'Get-WReparseSchemaVersion',
        'Test-WReparseWithinRoot', 'Get-WReparseCanonicalPath', 'Resolve-WReparseLinkTarget'
    )
    $actual = @(Get-Command -Module 'WReparse' -CommandType Function -ErrorAction SilentlyContinue |
        ForEach-Object { [string]$_.Name })
    if ($actual.Count -eq 0) { return 'the module surface could not be inspected (Get-Command -Module WReparse returned nothing)' }
    $extra = @($actual | Where-Object { $expected -notcontains $_ })
    if ($extra.Count -gt 0) {
        return "the module exports functions outside the contract surface: $($extra -join ', ')"
    }
    $missing = @($expected | Where-Object { $actual -notcontains $_ })
    if ($missing.Count -gt 0) { return "the module does not export: $($missing -join ', ')" }
    return $true
}

Add-WReparseCheck 'target-is-serialised-as-string' {
    if ($reportError) { return $reportError }
    $link = Get-WReparseTestRecord -Report $never -RelativePath 'link-rel'
    if ($null -eq $link) { return 'record link-rel is missing' }
    if ($null -ne $link.Target -and $link.Target -isnot [string]) {
        return "link-rel Target has type '$($link.Target.GetType().FullName)'; the contract defines Target as a single target string"
    }
    return $true
}

Add-WReparseCheck 'report-has-exactly-contract-fields' {
    if ($reportError) { return $reportError }
    $expected = @('SchemaVersion', 'Root', 'Records', 'Errors', 'Stats')
    $actual = @($never.PSObject.Properties | ForEach-Object { [string]$_.Name })
    $extra = @($actual | Where-Object { $expected -notcontains $_ })
    if ($extra.Count -gt 0) {
        return "the report carries fields the contract does not define: $($extra -join ', ')"
    }
    $missing = @($expected | Where-Object { $actual -notcontains $_ })
    if ($missing.Count -gt 0) { return "the report is missing contract fields: $($missing -join ', ')" }
    return $true
}

Add-WReparseCheck 'no-follow-produces-no-cycle-or-broken-target' {
    if ($reportError) { return $reportError }
    foreach ($code in @('cycle', 'broken_target')) {
        $hits = @($never.Errors | Where-Object { [string]$_.Code -eq $code })
        if ($hits.Count -gt 0) {
            return "a default (non-follow) scan produced '$code'; without -Follow the contract forbids cycle and broken_target"
        }
    }
    return $true
}

Add-WReparseCheck 'inscope-is-false-for-non-reparse-entries' {
    if ($reportError) { return $reportError }
    foreach ($path in @('plain.txt', 'docs', 'hardlink.txt')) {
        $record = Get-WReparseTestRecord -Report $never -RelativePath $path
        if ($null -eq $record) { return "record $path is missing" }
        if ($record.InScope -ne $false) {
            return "$path has Kind '$($record.Kind)' but InScope=$($record.InScope); InScope is only meaningful for reparse entries and is false otherwise"
        }
    }
    return $true
}


# ---- deepened contract checks (24, added by v1.3.0) --------------------------------------------------------------
Add-WReparseCheck 'culture-en-us-ordinal-order' {
    $prevT = [System.Threading.Thread]::CurrentThread.CurrentCulture
    try {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('en-US')
        $r = Get-WReparseReport -Root $scanRoot
        $p = @($r.Records | ForEach-Object { [string]$_.RelativePath })
        $z = [Array]::IndexOf($p, "$([char]0x5A).txt"); $a = [Array]::IndexOf($p, "$([char]0xC4).txt"); $o = [Array]::IndexOf($p, "$([char]0xF6).txt")
        if ($z -lt 0 -or $a -lt 0 -or $o -lt 0) { return 'Z/umlaut records missing' }
        if (-not ($z -lt $a -and $z -lt $o)) { return "en-US: ordinal order violated (Z=$z A=$a o=$o)" }
        return $true
    } finally { [System.Threading.Thread]::CurrentThread.CurrentCulture = $prevT }
}

Add-WReparseCheck 'culture-de-de-ordinal-order' {
    $prevT = [System.Threading.Thread]::CurrentThread.CurrentCulture
    try {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('de-DE')
        $r = Get-WReparseReport -Root $scanRoot
        $p = @($r.Records | ForEach-Object { [string]$_.RelativePath })
        $z = [Array]::IndexOf($p, "$([char]0x5A).txt"); $a = [Array]::IndexOf($p, "$([char]0xC4).txt"); $o = [Array]::IndexOf($p, "$([char]0xF6).txt")
        if ($z -lt 0 -or $a -lt 0 -or $o -lt 0) { return 'Z/umlaut records missing' }
        if (-not ($z -lt $a -and $z -lt $o)) { return "de-DE: ordinal order violated (Z=$z A=$a o=$o)" }
        return $true
    } finally { [System.Threading.Thread]::CurrentThread.CurrentCulture = $prevT }
}

Add-WReparseCheck 'culture-ja-jp-ordinal-order' {
    $prevT = [System.Threading.Thread]::CurrentThread.CurrentCulture
    try {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('ja-JP')
        $r = Get-WReparseReport -Root $scanRoot
        $p = @($r.Records | ForEach-Object { [string]$_.RelativePath })
        $z = [Array]::IndexOf($p, "$([char]0x5A).txt"); $a = [Array]::IndexOf($p, "$([char]0xC4).txt"); $o = [Array]::IndexOf($p, "$([char]0xF6).txt")
        if ($z -lt 0 -or $a -lt 0 -or $o -lt 0) { return 'Z/umlaut records missing' }
        if (-not ($z -lt $a -and $z -lt $o)) { return "ja-JP: ordinal order violated (Z=$z A=$a o=$o)" }
        return $true
    } finally { [System.Threading.Thread]::CurrentThread.CurrentCulture = $prevT }
}

Add-WReparseCheck 'deep-tree-emits-all-levels' {
    $cursor = $scanRoot
    for ($i = 1; $i -le 8; $i++) {
        $cursor = Join-Path $cursor ('level' + $i)
        $rec = Get-WReparseTestRecord -Report $never -RelativePath ($cursor.Substring($scanRoot.Length + 1))
        if ($null -eq $rec) { return "level$i is missing from the default scan" }
        if ([int]$rec.Depth -ne $i) { return "level$i Depth=$($rec.Depth), expected $i" }
        if ($rec.Kind -ne 'Directory') { return "level$i Kind=$($rec.Kind), expected Directory" }
    }
    $tip = Get-WReparseTestRecord -Report $never -RelativePath 'level1\level2\level3\level4\level5\level6\level7\level8\deepest.txt'
    if ($null -eq $tip) { return 'deepest.txt missing' }
    if ([int]$tip.Depth -ne 9) { return "deepest.txt Depth=$($tip.Depth), expected 9" }
    return $true
}

Add-WReparseCheck 'maxdepth-1-count-is-exact' {
    $direct = @(Get-ChildItem -LiteralPath $scanRoot -Force -ErrorAction SilentlyContinue)
    $r1 = Get-WReparseReport -Root $scanRoot -MaxDepth 1
    $expected = $direct.Count
    $actual = @($r1.Records).Count
    if ($actual -ne $expected) { return "MaxDepth 1 emitted $actual records, fixture has $expected direct children" }
    return $true
}

Add-WReparseCheck 'default-maxdepth-covers-deep-tree' {
    if ([int]$never.Stats.Directories -lt 9) { return "default scan found only $($never.Stats.Directories) directories; the 8-level chain was truncated" }
    $tip = Get-WReparseTestRecord -Report $never -RelativePath 'level1\level2\level3\level4\level5\level6\level7\level8\deepest.txt'
    if ($null -eq $tip) { return 'deepest.txt not emitted under the default -MaxDepth' }
    return $true
}

Add-WReparseCheck 'stats-sum-equals-record-count' {
    $sum = [int]$never.Stats.Directories + [int]$never.Stats.Files + [int]$never.Stats.ReparsePoints
    if ($sum -ne @($never.Records).Count) { return "Stats sum $sum != record count $(@($never.Records).Count)" }
    return $true
}

Add-WReparseCheck 'stats-match-kind-counts' {
    $d = @($never.Records | Where-Object { $_.Kind -eq 'Directory' }).Count
    $f = @($never.Records | Where-Object { $_.Kind -eq 'File' }).Count
    $r = @($never.Records | Where-Object { $_.Kind -eq 'ReparsePoint' }).Count
    if ([int]$never.Stats.Directories -ne $d) { return "Stats.Directories=$($never.Stats.Directories) but Kind=Directory count=$d" }
    if ([int]$never.Stats.Files -ne $f) { return "Stats.Files=$($never.Stats.Files) but Kind=File count=$f" }
    if ([int]$never.Stats.ReparsePoints -ne $r) { return "Stats.ReparsePoints=$($never.Stats.ReparsePoints) but Kind=ReparsePoint count=$r" }
    return $true
}

Add-WReparseCheck 'skipped-equals-unfollowed-reparse-count' {
    $rp = @($never.Records | Where-Object { $_.Kind -eq 'ReparsePoint' }).Count
    if ([int]$never.Stats.Skipped -ne $rp) { return "Skipped=$($never.Stats.Skipped) but only $rp reparse records exist" }
    if ([int]$follow.Stats.Skipped -ne 0) { return "with -Follow Skipped=$($follow.Stats.Skipped), expected 0" }
    return $true
}

Add-WReparseCheck 'canonical-folds-dot-dot' {
    $in = Join-Path (Join-Path $scanRoot 'docs') '..\data'
    $expect = Join-Path $scanRoot 'data'
    $actual = [string](Get-WReparseCanonicalPath -Path $in)
    if ($actual -cne $expect) { return "Get-WReparseCanonicalPath('$in')='$actual', expected '$expect'" }
    return $true
}

Add-WReparseCheck 'within-root-rejects-prefix-sibling' {
    $sibling = Join-Path (Split-Path -Parent $scanRoot) 'scanroot-extra'
    if (-not (Test-Path -LiteralPath $sibling)) { return "fixture sibling $sibling missing" }
    if (Test-WReparseWithinRoot -Path $sibling -Root $scanRoot) { return "$sibling reported inside $scanRoot; they only share a name prefix" }
    if (-not (Test-WReparseWithinRoot -Path (Join-Path $scanRoot 'docs') -Root $scanRoot)) { return 'real child reported outside the root' }
    return $true
}

Add-WReparseCheck 'resolve-absolute-target-normalised' {
    $expected = Join-Path $scanRoot 'docs'
    $abs = [string](Resolve-WReparseLinkTarget -LinkFullPath (Join-Path $scanRoot 'link-in') -RawTarget $expected)
    if ($abs -cne $expected) { return "absolute target resolved to '$abs', expected '$expected'" }
    $nullOut = Resolve-WReparseLinkTarget -LinkFullPath (Join-Path $scanRoot 'link-rel') -RawTarget ''
    if ($null -ne $nullOut) { return "empty RawTarget returned '$nullOut', expected `$null" }
    return $true
}

Add-WReparseCheck 'report-root-is-canonical' {
    $expected = [string](Get-WReparseCanonicalPath -Path $scanRoot)
    if ([string]$never.Root -cne $expected) { return "Root='$($never.Root)', canonical is '$expected'" }
    if ([string]$never.Root -ne [string]$follow.Root) { return 'Root differs between default and -Follow scans' }
    return $true
}

Add-WReparseCheck 'follow-prefix-uses-link-name' {
    $child = Get-WReparseTestRecord -Report $follow -RelativePath 'link-in\readme.txt'
    if ($null -eq $child) { return 'link-in\readme.txt missing under -Follow' }
    if ([string]$child.Kind -ne 'File') { return "link-in\readme.txt Kind=$($child.Kind)" }
    if ([int]$child.Depth -ne 2) { return "link-in\readme.txt Depth=$($child.Depth), expected 2" }
    return $true
}

Add-WReparseCheck 'follow-never-emits-target-real-name' {
    foreach ($p in @('outside\secret.txt')) {
        $rec = Get-WReparseTestRecord -Report $follow -RelativePath $p
        if ($null -ne $rec) { return "$p was emitted under -Follow; entries reached through a link must keep the link path prefix" }
    }
    return $true
}

Add-WReparseCheck 'follow-file-link-has-no-children' {
    $linkRec = Get-WReparseTestRecord -Report $follow -RelativePath 'link-file'
    if ($null -eq $linkRec) { return 'link-file record missing under -Follow' }
    $kids = @($follow.Records | Where-Object { $_.RelativePath -like 'link-file\*' })
    if ($kids.Count -ne 0) { return "link-file has $($kids.Count) child records; its target is a file" }
    return $true
}

Add-WReparseCheck 'follow-enters-twin-without-cycle' {
    $twin = Get-WReparseTestRecord -Report $follow -RelativePath 'link-twin'
    if ($null -eq $twin) { return 'link-twin missing under -Follow' }
    $kids = @($follow.Records | Where-Object { $_.RelativePath -like 'link-twin\*' })
    if ($kids.Count -eq 0) { return 'link-twin was not entered; two siblings pointing at the same target is not a cycle' }
    $cyc = @($follow.Errors | Where-Object { [string]$_.Code -eq 'cycle' })
    foreach ($c in $cyc) { if ([string]$c.RelativePath -eq 'link-twin') { return 'link-twin was reported as a cycle' } }
    return $true
}

Add-WReparseCheck 'follow-vs-default-record-relation' {
    $nDef = @($never.Records).Count
    $nFol = @($follow.Records).Count
    if ($nFol -le $nDef) { return "default scan has $nDef records, -Follow has $nFol; entering links must add records" }
    return $true
}

Add-WReparseCheck 'report-json-has-no-volatile-field' {
    $json = [string](ConvertTo-WReparseJson -Report $never)
    if ([string]::IsNullOrWhiteSpace($json)) { return 'serialised report is empty' }
    foreach ($bad in @('GeneratedAt', 'Timestamp', 'timestamp', 'ProcessId', 'PID', 'Random', 'Guid', 'guid')) {
        if ($json.Contains($bad)) { return "serialised report contains volatile field marker '$bad'" }
    }
    return $true
}

Add-WReparseCheck 'errors-serialise-as-empty-array' {
    if (@($never.Errors).Count -ne 0) { return "default scan produced $(@($never.Errors).Count) errors on a healthy fixture" }
    $json = [string](ConvertTo-WReparseJson -Report $never)
    if ($json -notmatch '"Errors"\s*:\s*\[\s*\]') { return 'Errors did not serialise as an empty array' }
    return $true
}

Add-WReparseCheck 'schema-version-is-constant' {
    if ([string](Get-WReparseSchemaVersion) -ne [string]$never.SchemaVersion) { return "Get-WReparseSchemaVersion differs from report SchemaVersion" }
    if ([string]$never.SchemaVersion -ne 'wreparse/1.0') { return "SchemaVersion='$($never.SchemaVersion)'" }
    return $true
}

Add-WReparseCheck 'record-fields-match-contract-exactly' {
    $want = @('RelativePath','Kind','ReparseKind','Target','ResolvedTarget','InScope','Depth','Size')
    foreach ($rec in @($never.Records | Select-Object -First 12)) {
        $got = @($rec.PSObject.Properties.Name)
        if (($got -join ',') -ne ($want -join ',')) { return "record '$($rec.RelativePath)' fields are [$($got -join ',')]" }
    }
    return $true
}

Add-WReparseCheck 'size-zero-for-non-file-records' {
    foreach ($rec in @($never.Records | Where-Object { $_.Kind -ne 'File' })) {
        if ([int64]$rec.Size -ne 0) { return "'$($rec.RelativePath)' Kind=$($rec.Kind) Size=$($rec.Size), expected 0" }
    }
    return $true
}

Add-WReparseCheck 'non-reparse-null-fields-stay-null' {
    foreach ($rec in @($never.Records | Where-Object { $_.Kind -ne 'ReparsePoint' })) {
        if ($null -ne $rec.ReparseKind) { return "'$($rec.RelativePath)' ReparseKind=$($rec.ReparseKind), expected null" }
        if ($null -ne $rec.Target) { return "'$($rec.RelativePath)' Target=$($rec.Target), expected null" }
        if ($null -ne $rec.ResolvedTarget) { return "'$($rec.RelativePath)' ResolvedTarget=$($rec.ResolvedTarget), expected null" }
    }
    return $true
}

# ---- persist ---------------------------------------------------------------
$checksDirectory = Split-Path -Parent $ChecksPath
if (-not (Test-Path -LiteralPath $checksDirectory)) { New-Item -ItemType Directory -Path $checksDirectory -Force | Out-Null }

$payload = [pscustomobject][ordered]@{
    task_id      = 'wfflab__wreparse-217'
    task_version = '1.3.0'
    scan_root    = $scanRoot
    checks       = @($results.ToArray())
}
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ChecksPath -Encoding UTF8

$failed = @($results | Where-Object { $_.status -ne 'PASS' }).Count
Write-Host ("checks: {0} passed, {1} failed, {2} total" -f ($results.Count - $failed), $failed, $results.Count)

if ($failed -gt 0) { exit 1 }
exit 0
