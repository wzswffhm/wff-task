# WReparse - Model.ps1
# Shared vocabulary: error codes, enumerations, and factory helpers.
# Part of the WReparse reference implementation. See docs/REPARSE-CONTRACT.md.

Set-StrictMode -Version Latest

# Error codes are part of the public contract. Order is stable and is not
# sorted at serialisation time; callers match on the literal string.
$script:WReparseErrorCode = @(
    'not_found'
    'access_denied'
    'cycle'
    'broken_target'
    'structure'
    'too_deep'
    'invalid_argument'
)

$script:WReparseSchemaVersion = 'wreparse/1.0'

# Entry kinds. A hard link is a FILE, not a reparse point: the two NTFS
# directory entries share one data stream and neither entry carries a
# reparse attribute. Only entries whose file attributes contain
# FILE_ATTRIBUTE_REPARSE_POINT are reported with Kind = 'ReparsePoint'.
$script:WReparseKindDirectory = 'Directory'
$script:WReparseKindFile = 'File'
$script:WReparseKindReparse = 'ReparsePoint'

function Get-WReparseErrorCode {
    [CmdletBinding()]
    param()
    return $script:WReparseErrorCode
}

function Get-WReparseSchemaVersion {
    [CmdletBinding()]
    param()
    return $script:WReparseSchemaVersion
}

function New-WReparseError {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Code,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if ($script:WReparseErrorCode -notcontains $Code) {
        throw "Unknown WReparse error code: $Code"
    }
    return [pscustomobject][ordered]@{
        RelativePath = $RelativePath
        Code         = $Code
        Message      = $Message
    }
}

function New-WReparseRecord {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Kind,
        $ReparseKind = $null,
        $Target = $null,
        $ResolvedTarget = $null,
        [bool]$InScope = $false,
        [int]$Depth = 0,
        [long]$Size = 0
    )
    return [pscustomobject][ordered]@{
        RelativePath   = $RelativePath
        Kind           = $Kind
        ReparseKind    = $ReparseKind
        Target         = $Target
        ResolvedTarget = $ResolvedTarget
        InScope        = $InScope
        Depth          = $Depth
        Size           = $Size
    }
}

function New-WReparseStats {
    [CmdletBinding()]
    param(
        [int]$Directories = 0,
        [int]$Files = 0,
        [int]$ReparsePoints = 0,
        [int]$Skipped = 0,
        [int]$Errors = 0
    )
    return [pscustomobject][ordered]@{
        Directories   = $Directories
        Files         = $Files
        ReparsePoints = $ReparsePoints
        Skipped       = $Skipped
        Errors        = $Errors
    }
}

function New-WReparseReport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Records,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Errors,
        [Parameter(Mandatory = $true)][object]$Stats
    )
    return [pscustomobject][ordered]@{
        SchemaVersion = $script:WReparseSchemaVersion
        Root          = $Root
        Records       = @($Records)
        Errors        = @($Errors)
        Stats         = $Stats
    }
}
