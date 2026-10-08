# WReparse - directory walker
# Safe directory enumeration: reparse classification, containment, cycle and
# depth control. Part of the WReparse reference implementation.

function Get-WReparseMemberValue {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

# Maps the provider link type to the contract vocabulary. Only entries whose
# file attributes carry FILE_ATTRIBUTE_REPARSE_POINT reach this function, so a
# hard link (which has a link type but no reparse attribute) is never mapped.
function Get-WReparseKindFromLinkType {
    [CmdletBinding()]
    param([AllowNull()][string]$LinkType)
    switch ($LinkType) {
        'SymbolicLink' { return 'SymbolicLink' }
        'Junction' { return 'SymbolicLink' }
        'MountPoint' { return 'MountPoint' }
        default { return 'Unknown' }
    }
}

function Test-WReparseIsReparsePoint {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Item)
    $linkType = Get-WReparseMemberValue -InputObject $Item -Name 'LinkType'
    return -not [string]::IsNullOrWhiteSpace([string]$linkType)
}

function Add-WReparseError {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][hashtable]$State,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Code,
        [Parameter(Mandatory = $true)][string]$Message
    )
    [void]$State.Errors.Add((New-WReparseError -RelativePath $RelativePath -Code $Code -Message $Message))
}

function Invoke-WReparseDirectoryWalk {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RealDirectory,
        [Parameter(Mandatory = $true)][string]$VirtualDirectory,
        [Parameter(Mandatory = $true)][int]$Depth,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Ancestry,
        [Parameter(Mandatory = $true)][hashtable]$State
    )
    if ($Depth -ge $State.MaxDepth) {
        $relative = Get-WReparseRelativePath -FullPath $VirtualDirectory -Root $State.Root
        Add-WReparseError -State $State -RelativePath $relative -Code 'too_deep' `
            -Message "Depth limit of $($State.MaxDepth) reached; not enumerating."
        return
    }

    $children = @()
    try {
        $children = @(Get-ChildItem -LiteralPath $RealDirectory -Force -ErrorAction Stop)
    }
    catch [System.UnauthorizedAccessException] {
        $relative = Get-WReparseRelativePath -FullPath $VirtualDirectory -Root $State.Root
        Add-WReparseError -State $State -RelativePath $relative -Code 'access_denied' `
            -Message 'Access denied while enumerating the directory.'
        return
    }
    catch {
        $relative = Get-WReparseRelativePath -FullPath $VirtualDirectory -Root $State.Root
        Add-WReparseError -State $State -RelativePath $relative -Code 'access_denied' `
            -Message $_.Exception.Message
        return
    }

    foreach ($child in $children) {
        $childDepth = $Depth + 1
        $realChild = Get-WReparseMemberValue -InputObject $child -Name 'FullName'
        $virtualChild = Join-Path $VirtualDirectory (Split-Path -Leaf $realChild)
        $relative = Get-WReparseRelativePath -FullPath $virtualChild -Root $State.Root

        if (Test-WReparseIsReparsePoint -Item $child) {
            $linkType = [string](Get-WReparseMemberValue -InputObject $child -Name 'LinkType')
            $rawTargetValue = Get-WReparseMemberValue -InputObject $child -Name 'Target'
            # The provider exposes Target as a string[] (a reparse point may
            # carry several substitutions); the contract keeps the first one.
            if ($null -eq $rawTargetValue) {
                $rawTarget = $null
            }
            elseif ($rawTargetValue -is [string]) {
                $rawTarget = $rawTargetValue
            }
            else {
                $rawTarget = [string](@($rawTargetValue) | Select-Object -First 1)
            }
            $resolved = Resolve-WReparseLinkTarget -LinkFullPath $realChild -RawTarget $rawTarget
            $inScope = $false
            if ($null -ne $resolved) {
                $inScope = Test-WReparseWithinRoot -Path $resolved -Root $State.Root
            }
            [void]$State.Records.Add((New-WReparseRecord -RelativePath $relative -Kind 'ReparsePoint' `
                -ReparseKind (Get-WReparseKindFromLinkType -LinkType $linkType) `
                -Target $rawTarget -ResolvedTarget $resolved -InScope $inScope `
                -Depth $Depth -Size 0))

            if (-not $State.Follow) {
                $State.Skipped++
                continue
            }
            if ($null -eq $resolved) {
                Add-WReparseError -State $State -RelativePath $relative -Code 'broken_target' `
                    -Message 'The reparse target could not be resolved.'
                continue
            }
            if (-not (Test-Path -LiteralPath $resolved)) {
                Add-WReparseError -State $State -RelativePath $relative -Code 'broken_target' `
                    -Message 'The reparse target does not exist.'
                continue
            }
            if ($Ancestry -contains $resolved) {
                Add-WReparseError -State $State -RelativePath $relative -Code 'cycle' `
                    -Message 'The reparse target is an ancestor already visited on this branch.'
                continue
            }
            if (Test-Path -LiteralPath $resolved -PathType Container) {
                Invoke-WReparseDirectoryWalk -RealDirectory $resolved -VirtualDirectory $virtualChild `
                    -Depth $childDepth -Ancestry ($Ancestry + $resolved) -State $State
            }
            continue
        }

        $isContainer = [bool](Get-WReparseMemberValue -InputObject $child -Name 'PSIsContainer')
        $size = 0
        if (-not $isContainer) {
            $length = Get-WReparseMemberValue -InputObject $child -Name 'Length'
            if ($null -ne $length) { $size = [long]$length }
        }
        $kind = if ($isContainer) { 'Directory' } else { 'File' }
        [void]$State.Records.Add((New-WReparseRecord -RelativePath $relative -Kind $kind `
            -Depth $Depth -Size $size))

        if ($isContainer) {
            $realChildCanonical = Get-WReparseCanonicalPath $realChild
            Invoke-WReparseDirectoryWalk -RealDirectory $realChildCanonical -VirtualDirectory $virtualChild `
                -Depth $childDepth -Ancestry ($Ancestry + $realChildCanonical) -State $State
        }
    }
}

function Invoke-WReparseWalk {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [ValidateSet('Never', 'Always')][string]$FollowMode = 'Never',
        [int]$MaxDepth = 32
    )
    $state = @{
        Records  = New-Object System.Collections.ArrayList
        Errors   = New-Object System.Collections.ArrayList
        Skipped  = 0
        Root     = $null
        Follow   = $true
        MaxDepth = [Math]::Max(0, $MaxDepth)
    }

    $canonicalRoot = $null
    try { $canonicalRoot = Get-WReparseCanonicalPath $Root }
    catch {
        Add-WReparseError -State $state -RelativePath '.' -Code 'invalid_argument' -Message $_.Exception.Message
        return [pscustomobject]@{ Records = @(); Errors = $state.Errors.ToArray(); Skipped = 0 }
    }

    if (-not (Test-Path -LiteralPath $canonicalRoot)) {
        Add-WReparseError -State $state -RelativePath '.' -Code 'not_found' `
            -Message "Scan root does not exist: $canonicalRoot"
        return [pscustomobject]@{ Records = @(); Errors = $state.Errors.ToArray(); Skipped = 0 }
    }
    if (-not (Test-Path -LiteralPath $canonicalRoot -PathType Container)) {
        Add-WReparseError -State $state -RelativePath '.' -Code 'structure' `
            -Message "Scan root is not a directory: $canonicalRoot"
        return [pscustomobject]@{ Records = @(); Errors = $state.Errors.ToArray(); Skipped = 0 }
    }

    $state.Root = $canonicalRoot
    Invoke-WReparseDirectoryWalk -RealDirectory $canonicalRoot -VirtualDirectory $canonicalRoot `
        -Depth 0 -Ancestry @($canonicalRoot) -State $state

    return [pscustomobject]@{
        Records = $state.Records.ToArray()
        Errors  = $state.Errors.ToArray()
        Skipped = $state.Skipped
    }
}
