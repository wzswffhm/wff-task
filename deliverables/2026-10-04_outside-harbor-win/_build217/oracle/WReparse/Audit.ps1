# WReparse - Audit.ps1
# Deterministic ordering, statistics and serialisation.
# Part of the WReparse reference implementation.

# Stable merge sort so the report never depends on the enumerator order or on
# the host culture. Sort-Object is deliberately not used: its default string
# comparison is culture-aware and would order non-ASCII names differently on
# different hosts.
function Sort-WReparseStable {
    [CmdletBinding()]
    param(
        [AllowEmptyCollection()][object[]]$Items,
        [Parameter(Mandatory = $true)][scriptblock]$KeySelector
    )
    $array = @($Items)
    if ($array.Count -le 1) { return @($array) }
    $middle = [int]($array.Count / 2)
    $left = @(Sort-WReparseStable -Items @($array[0..($middle - 1)]) -KeySelector $KeySelector)
    $right = @(Sort-WReparseStable -Items @($array[$middle..($array.Count - 1)]) -KeySelector $KeySelector)
    $merged = New-Object System.Collections.ArrayList
    $i = 0
    $j = 0
    while ($i -lt $left.Count -and $j -lt $right.Count) {
        $leftKey = [string](& $KeySelector $left[$i])
        $rightKey = [string](& $KeySelector $right[$j])
        if ((Compare-WReparsePath -Left $leftKey -Right $rightKey) -le 0) {
            [void]$merged.Add($left[$i]); $i++
        }
        else {
            [void]$merged.Add($right[$j]); $j++
        }
    }
    while ($i -lt $left.Count) { [void]$merged.Add($left[$i]); $i++ }
    while ($j -lt $right.Count) { [void]$merged.Add($right[$j]); $j++ }
    return @($merged.ToArray())
}

function Get-WReparseStats {
    [CmdletBinding()]
    param(
        [AllowEmptyCollection()][object[]]$Records,
        [int]$Skipped = 0,
        [int]$ErrorCount = 0
    )
    $directories = 0
    $files = 0
    $reparse = 0
    foreach ($record in @($Records)) {
        switch ($record.Kind) {
            'Directory' { $directories++ }
            'File' { $files++ }
            'ReparsePoint' { $reparse++ }
        }
    }
    return New-WReparseStats -Directories $directories -Files $files -ReparsePoints $reparse `
        -Skipped $Skipped -Errors $ErrorCount
}

function Get-WReparseReport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [int]$MaxDepth = 32,
        [switch]$Follow
    )
    $followMode = if ($Follow) { 'Always' } else { 'Never' }
    $walk = Invoke-WReparseWalk -Root $Root -FollowMode $followMode -MaxDepth $MaxDepth
    $records = @(Sort-WReparseStable -Items @($walk.Records) -KeySelector { param($r) $r.RelativePath })
    $errors = @(Sort-WReparseStable -Items @($walk.Errors) -KeySelector {
            param($e) ($e.RelativePath + [string][char]0 + $e.Code)
        })
    $stats = Get-WReparseStats -Records $records -Skipped $walk.Skipped -ErrorCount $errors.Count
    $canonicalRoot = $null
    try { $canonicalRoot = Get-WReparseCanonicalPath $Root } catch { $canonicalRoot = $Root }
    return New-WReparseReport -Root $canonicalRoot -Records $records -Errors $errors -Stats $stats
}

function ConvertTo-WReparseJson {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Report
    )
    return ($Report | ConvertTo-Json -Depth 12)
}
