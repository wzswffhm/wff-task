# WReparse - path semantics
# Canonicalisation, directory-boundary containment, and link-target resolution.
# Part of the WReparse implementation. See the contract under docs/

# Canonical form used for every comparison and for the report:
#   * full (rooted) path with '.' and '..' collapsed
#   * no trailing directory separator, except for a volume root ('C:\')
#     or a UNC share root
#   * original casing preserved
function Get-WReparseCanonicalPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.Length -le 3) { return $full }
    if ($full -match '^[\\/]{2}[^\\/]+[\\/][^\\/]+$') { return $full }
    $trimmed = $full.TrimEnd([char]'\', [char]'/')
    if ($trimmed.Length -eq 2 -and $trimmed[1] -eq ':') { return $trimmed + '\' }
    return $trimmed
}

# Directory-boundary aware containment. 'C:\root2' is NOT inside 'C:\root'
# even though 'C:\root2'.StartsWith('C:\root') is true. Windows path
# comparison is case-insensitive, so the ordinal-ignore-case comparer is used.
function Test-WReparseWithinRoot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root
    )
    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) {
        return $false
    }
    $p = Get-WReparseCanonicalPath $Path
    $r = Get-WReparseCanonicalPath $Root
    if ([System.StringComparer]::OrdinalIgnoreCase.Equals($p, $r)) { return $true }
    $prefix = $r
    if (-not $prefix.EndsWith('\')) { $prefix = $prefix + '\' }
    return $p.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

# Relative path of a scanned entry with respect to the scan root, using the
# Windows separator. The root itself yields '.'.
function Get-WReparseRelativePath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$FullPath,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $p = Get-WReparseCanonicalPath $FullPath
    $r = Get-WReparseCanonicalPath $Root
    if ([System.StringComparer]::OrdinalIgnoreCase.Equals($p, $r)) { return '.' }
    $prefix = $r
    if (-not $prefix.EndsWith('\')) { $prefix = $prefix + '\' }
    if ($p.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $p.Substring($prefix.Length)
    }
    return $p
}

# The reparse target stored on disk may be relative. A relative target is
# resolved against the directory that CONTAINS the link, never against the
# process working directory and never against the scan root.
function Resolve-WReparseLinkTarget {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$LinkFullPath,
        [AllowNull()][string]$RawTarget
    )
    if ([string]::IsNullOrWhiteSpace($RawTarget)) { return $null }
    $candidate = $null
    if ([System.IO.Path]::IsPathRooted($RawTarget)) {
        $candidate = $RawTarget
    }
    else {
        $linkCanonical = Get-WReparseCanonicalPath $LinkFullPath
        $linkDirectory = Split-Path -Parent $linkCanonical
        if ([string]::IsNullOrWhiteSpace($linkDirectory)) { return $null }
        $candidate = Join-Path $linkDirectory $RawTarget
    }
    try {
        return Get-WReparseCanonicalPath $candidate
    }
    catch {
        return $null
    }
}

# Stable ordering key: ordinal, case-insensitive first, with a case-sensitive
# tie-break so that two entries whose names differ only by case keep a
# deterministic position.
function Compare-WReparsePath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )
    $primary = [System.StringComparer]::OrdinalIgnoreCase.Compare($Left, $Right)
    if ($primary -ne 0) { return $primary }
    return [System.StringComparer]::Ordinal.Compare($Left, $Right)
}
