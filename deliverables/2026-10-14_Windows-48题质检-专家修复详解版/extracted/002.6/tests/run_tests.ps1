[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$started = Get-Date
$checks = @()
$status = 'RESOLVED'
$invalidReason = $null
$tempRoot = Join-Path $env:TEMP ('windows-powershell-ads-' + [guid]::NewGuid().ToString('N'))
# Every check below is a required testcase of the frozen contract. The shipped entrypoint
# rejects evidence whose JUnit case set differs from contract.required_test_ids, so no check
# may be gated behind a task.toml difficulty read that a packed payload cannot even resolve.

function Add-Check {
    param(
        [string]$Id,
        [string]$Category,
        [scriptblock]$Assertion
    )

    try {
        & $Assertion
        $script:checks += [pscustomobject]@{
            test_id = $Id
            category = $Category
            passed = $true
            failure_reason = $null
        }
    }
    catch {
        $script:checks += [pscustomobject]@{
            test_id = $Id
            category = $Category
            passed = $false
            failure_reason = $_.Exception.Message
        }
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw ($Message + ' Actual=' + [string]$Actual + ' Expected=' + [string]$Expected)
    }
}

function Get-NamedStreamText {
    param(
        [string]$Path,
        [string]$StreamName
    )

    $streams = @(Get-Item -LiteralPath $Path -Stream * -Force -ErrorAction SilentlyContinue | Where-Object { $_.Stream -ieq $StreamName })
    if ($streams.Count -eq 0) {
        return $null
    }

    return (Get-Content -LiteralPath $Path -Stream $streams[0].Stream -Raw)
}

function Get-FileSnapshot {
    param([string]$Path)

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    [pscustomobject]@{
        Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
        Length = $item.Length
        Attributes = $item.Attributes
        Identity = Get-FileIdentity -Path $Path
    }
}

function Get-FileTimes {
    param([string]$Path)

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    [pscustomobject]@{
        CreationTimeUtc = $item.CreationTimeUtc
        LastAccessTimeUtc = $item.LastAccessTimeUtc
        LastWriteTimeUtc = $item.LastWriteTimeUtc
    }
}

function Set-FixtureTimes {
    param(
        [string]$Path,
        [datetime]$Seed
    )

    [System.IO.File]::SetCreationTimeUtc($Path, $Seed)
    [System.IO.File]::SetLastWriteTimeUtc($Path, $Seed.AddMinutes(1))
}

function Get-FileIdentity {
    param([string]$Path)

    if ($null -eq ('WindowsFileIdentityProbe' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class WindowsFileIdentityProbe
{
    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation
    {
        public uint FileAttributes;
        public long CreationTime;
        public long LastAccessTime;
        public long LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle fileHandle,
        out ByHandleFileInformation information);

    public static string Get(string path)
    {
        const uint FileReadAttributes = 0x80;
        const uint FileShareRead = 0x1;
        const uint FileShareWrite = 0x2;
        const uint FileShareDelete = 0x4;
        const uint OpenExisting = 0x3;

        using (SafeFileHandle handle = CreateFile(
            path,
            FileReadAttributes,
            FileShareRead | FileShareWrite | FileShareDelete,
            IntPtr.Zero,
            OpenExisting,
            0,
            IntPtr.Zero))
        {
            if (handle.IsInvalid)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            ByHandleFileInformation information;
            if (!GetFileInformationByHandle(handle, out information))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            ulong index = ((ulong)information.FileIndexHigh << 32) | information.FileIndexLow;
            return information.VolumeSerialNumber.ToString("X8") + ":" + index.ToString("X16");
        }
    }
}
'@
    }

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    return [WindowsFileIdentityProbe]::Get($item.FullName)
}

function Assert-ResultContract {
    param(
        [object[]]$Results,
        [string[]]$Inputs
    )

    Assert-Equal @($Results).Count @($Inputs).Count 'The result count must match the input count.'
    for ($index = 0; $index -lt @($Inputs).Count; $index++) {
        $result = $Results[$index]
        $properties = @($result.PSObject.Properties.Name)
        Assert-True ($properties -contains 'Path') 'A result is missing Path.'
        Assert-True ($properties -contains 'Status') 'A result is missing Status.'
        Assert-True ($properties -contains 'Error') 'A result is missing Error.'
        Assert-Equal $result.Path $Inputs[$index] 'Result Path must echo the raw input in order.'
        Assert-True (@('Removed', 'AlreadyClean', 'Failed') -contains $result.Status) 'Result Status is outside the contract.'
        if ($result.Status -eq 'Failed') {
            Assert-True (-not [string]::IsNullOrWhiteSpace([string]$result.Error)) 'Failed results need a readable Error.'
        }
        else {
            Assert-True ([string]::IsNullOrEmpty([string]$result.Error)) 'Successful results must have an empty Error.'
        }
    }
}

function Invoke-CleanerSafely {
    param([string[]]$Inputs)

    try {
        return @(Clear-ZoneIdentifier -Path $Inputs)
    }
    catch {
        return @([pscustomobject]@{
            Path = $null
            Status = 'InvocationFailed'
            Error = $_.Exception.Message
        })
    }
}

function Invoke-CleanerWithOptions {
    param(
        [string[]]$Inputs,
        [switch]$Atomic,
        [switch]$WhatIf,
        [string]$AuditPath
    )

    $arguments = @{ Path = $Inputs }
    if ($Atomic) { $arguments.Atomic = $true }
    if ($WhatIf) { $arguments.WhatIf = $true }
    if ($PSBoundParameters.ContainsKey('AuditPath')) { $arguments.AuditPath = $AuditPath }
    try {
        return @(Clear-ZoneIdentifier @arguments)
    }
    catch {
        return @([pscustomobject]@{
            Path = $null
            Status = 'InvocationFailed'
            Error = $_.Exception.Message
        })
    }
}

. (Join-Path $PSScriptRoot 'atomic_success_state.ps1')

try {
    if ($env:OS -ne 'Windows_NT') {
        $status = 'INVALID'
        $invalidReason = 'This evaluator requires Windows.'
    }
    else {
        $sourcePath = Join-Path $WorkspaceRoot 'src\ZoneMarkCleaner.ps1'
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            $status = 'INVALID'
            $invalidReason = 'Workspace source file is missing.'
        }
        else {
            . $sourcePath

            $fixtureDir = Join-Path $tempRoot (([char]0x76EE) + ([char]0x5F55) + ' with spaces')
            New-Item -ItemType Directory -Force -Path $fixtureDir | Out-Null

            $markedPath = Join-Path $fixtureDir 'report [A].txt'
            $primaryContent = "primary-" + ([char]0x5185) + ([char]0x5BB9) + "`nline-2"
            [System.IO.File]::WriteAllText($markedPath, $primaryContent, (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $markedPath -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-Content -LiteralPath $markedPath -Stream 'AuditTag' -Value 'audit-content' -Encoding UTF8
            Set-Content -LiteralPath $markedPath -Stream 'Zone.Identifier.bak' -Value 'backup-content' -Encoding UTF8
            $markedTimeSeed = [datetime]::Parse('2022-03-04T05:06:07.8900000Z').ToUniversalTime()
            Set-FixtureTimes -Path $markedPath -Seed $markedTimeSeed
            $markedBefore = Get-FileSnapshot -Path $markedPath
            $markedTimesBefore = Get-FileTimes -Path $markedPath
            $auditBefore = Get-NamedStreamText -Path $markedPath -StreamName 'AuditTag'
            $backupBefore = Get-NamedStreamText -Path $markedPath -StreamName 'Zone.Identifier.bak'

            $firstRun = @(Invoke-CleanerSafely -Inputs $markedPath)
            $markedTimesAfter = Get-FileTimes -Path $markedPath
            Add-Check -Id 'F2P-01-result-removed' -Category 'FAIL_TO_PASS' {
                Assert-Equal $firstRun.Count 1 'The marked-file call must return one result.'
                Assert-Equal $firstRun[0].Status 'Removed' 'A marked file must report Removed.'
            }
            Add-Check -Id 'F2P-02-zone-stream-removed' -Category 'FAIL_TO_PASS' {
                Assert-True ((Get-NamedStreamText -Path $markedPath -StreamName 'Zone.Identifier') -eq $null) 'Zone.Identifier remains.'
            }
            Add-Check -Id 'F2P-03-main-content' -Category 'FAIL_TO_PASS' {
                $after = Get-FileSnapshot -Path $markedPath
                Assert-Equal $after.Hash $markedBefore.Hash 'Primary file hash changed.'
                Assert-Equal $after.Length $markedBefore.Length 'Primary file length changed.'
                Assert-True (Test-Path -LiteralPath $markedPath -PathType Leaf) 'Primary file was deleted.'
            }
            Add-Check -Id 'F2P-04-other-streams' -Category 'FAIL_TO_PASS' {
                Assert-Equal (Get-NamedStreamText -Path $markedPath -StreamName 'AuditTag') $auditBefore 'AuditTag changed or was removed.'
                Assert-Equal (Get-NamedStreamText -Path $markedPath -StreamName 'Zone.Identifier.bak') $backupBefore 'Zone.Identifier.bak changed or was removed.'
            }
            Add-Check -Id 'F2P-05-attributes-preserved' -Category 'FAIL_TO_PASS' {
                $after = Get-FileSnapshot -Path $markedPath
                Assert-Equal $after.Attributes $markedBefore.Attributes 'Ordinary file attributes changed.'
            }
            Add-Check -Id 'F2P-11-file-identity' -Category 'FAIL_TO_PASS' {
                $after = Get-FileSnapshot -Path $markedPath
                Assert-Equal $after.Identity $markedBefore.Identity 'The primary file was replaced instead of editing its stream.'
            }
            Add-Check -Id 'F2P-12-timestamps-preserved' -Category 'FAIL_TO_PASS' {
                Assert-Equal $markedTimesAfter.CreationTimeUtc $markedTimesBefore.CreationTimeUtc 'Creation time changed.'
                Assert-Equal $markedTimesAfter.LastWriteTimeUtc $markedTimesBefore.LastWriteTimeUtc 'Last write time changed.'
            }
            $casePath = Join-Path $fixtureDir 'case-variant.txt'
            [System.IO.File]::WriteAllText($casePath, 'case-content', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $casePath -Stream 'zone.identifier' -Value 'ZoneId=3' -Encoding UTF8
            $caseRun = @(Invoke-CleanerSafely -Inputs $casePath)
            Add-Check -Id 'F2P-10-case-insensitive-zone' -Category 'FAIL_TO_PASS' {
                Assert-Equal $caseRun.Count 1 'The case-variant call must return one result.'
                Assert-Equal $caseRun[0].Status 'Removed' 'Stream matching must be case-insensitive.'
                Assert-True ((Get-NamedStreamText -Path $casePath -StreamName 'Zone.Identifier') -eq $null) 'The case-variant Zone.Identifier remains.'
            }

            $protectedPath = Join-Path $fixtureDir 'readonly-hidden.txt'
            [System.IO.File]::WriteAllText($protectedPath, 'protected-content', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $protectedPath -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-Content -LiteralPath $protectedPath -Stream 'AuditTag' -Value 'protected-audit' -Encoding UTF8
            $protectedTimeSeed = [datetime]::Parse('2023-07-08T09:10:11.1200000Z').ToUniversalTime()
            Set-FixtureTimes -Path $protectedPath -Seed $protectedTimeSeed
            Set-ItemProperty -LiteralPath $protectedPath -Name Attributes -Value ([System.IO.FileAttributes]::ReadOnly -bor [System.IO.FileAttributes]::Hidden)
            $protectedBefore = Get-FileSnapshot -Path $protectedPath
            $protectedTimesBefore = Get-FileTimes -Path $protectedPath
            $protectedAuditBefore = Get-NamedStreamText -Path $protectedPath -StreamName 'AuditTag'
            $protectedRun = @(Invoke-CleanerSafely -Inputs $protectedPath)
            $protectedTimesAfter = Get-FileTimes -Path $protectedPath
            Add-Check -Id 'F2P-06-readonly-removed' -Category 'FAIL_TO_PASS' {
                Assert-Equal $protectedRun.Count 1 'The protected-file call must return one result.'
                Assert-Equal $protectedRun[0].Status 'Removed' 'Read-only files must be cleaned successfully.'
                Assert-True ((Get-NamedStreamText -Path $protectedPath -StreamName 'Zone.Identifier') -eq $null) 'Zone.Identifier remains on the protected file.'
            }
            Add-Check -Id 'F2P-07-readonly-attributes' -Category 'FAIL_TO_PASS' {
                $after = Get-FileSnapshot -Path $protectedPath
                Assert-Equal $after.Attributes $protectedBefore.Attributes 'ReadOnly/Hidden attributes were not restored.'
            }
            Add-Check -Id 'F2P-08-readonly-content' -Category 'FAIL_TO_PASS' {
                $after = Get-FileSnapshot -Path $protectedPath
                Assert-Equal $after.Hash $protectedBefore.Hash 'Protected primary file hash changed.'
                Assert-Equal $after.Length $protectedBefore.Length 'Protected primary file length changed.'
            }
            Add-Check -Id 'F2P-09-readonly-other-stream' -Category 'FAIL_TO_PASS' {
                Assert-Equal (Get-NamedStreamText -Path $protectedPath -StreamName 'AuditTag') $protectedAuditBefore 'Protected unrelated stream changed.'
            }
            Add-Check -Id 'F2P-13-readonly-timestamps' -Category 'FAIL_TO_PASS' {
                Assert-Equal $protectedTimesAfter.CreationTimeUtc $protectedTimesBefore.CreationTimeUtc 'Protected creation time changed.'
                Assert-Equal $protectedTimesAfter.LastWriteTimeUtc $protectedTimesBefore.LastWriteTimeUtc 'Protected last write time changed.'
            }

            $cleanRun = @(Invoke-CleanerSafely -Inputs $markedPath)
            Add-Check -Id 'PASS-01-clean-idempotent' -Category 'PASS_TO_PASS' {
                Assert-Equal $cleanRun.Count 1 'An idempotent call must return one result.'
                Assert-Equal $cleanRun[0].Status 'AlreadyClean' 'A clean file must report AlreadyClean.'
            }

            $duplicatePath = Join-Path $fixtureDir 'duplicate.txt'
            [System.IO.File]::WriteAllText($duplicatePath, 'duplicate-content', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $duplicatePath -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $duplicateRun = @(Invoke-CleanerSafely -Inputs @($duplicatePath, $duplicatePath))
            Add-Check -Id 'PASS-04-duplicate-order' -Category 'PASS_TO_PASS' {
                Assert-Equal $duplicateRun.Count 2 'Duplicate inputs must produce two results.'
                Assert-Equal $duplicateRun[0].Status 'Removed' 'The first duplicate must remove the stream.'
                Assert-Equal $duplicateRun[1].Status 'AlreadyClean' 'The second duplicate must observe the clean state.'
                Assert-Equal $duplicateRun[0].Path $duplicatePath 'The first duplicate path was not echoed.'
                Assert-Equal $duplicateRun[1].Path $duplicatePath 'The second duplicate path was not echoed.'
            }

            $continuationPath = Join-Path $fixtureDir 'continuation.txt'
            [System.IO.File]::WriteAllText($continuationPath, 'continuation-content', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $continuationPath -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $missingPath = Join-Path $fixtureDir 'missing.txt'
            $mixedInputs = @($missingPath, $continuationPath)
            $mixedRun = @(Invoke-CleanerSafely -Inputs $mixedInputs)
            Add-Check -Id 'PASS-02-mixed-continuation' -Category 'PASS_TO_PASS' {
                Assert-Equal $mixedRun.Count 2 'A mixed batch must return one result per input.'
                Assert-Equal $mixedRun[0].Status 'Failed' 'The missing path must be Failed.'
                Assert-Equal $mixedRun[1].Status 'Removed' 'A valid path after a failure must still be processed.'
                Assert-True ((Get-NamedStreamText -Path $continuationPath -StreamName 'Zone.Identifier') -eq $null) 'The valid path after a failure was not cleaned.'
            }

            $wildcardPath = Join-Path $fixtureDir '*.txt'
            $invalidInputs = @('', '   ', $missingPath, $fixtureDir, $wildcardPath)
            $invalidRun = @(Invoke-CleanerSafely -Inputs $invalidInputs)
            Add-Check -Id 'PASS-03-invalid-inputs' -Category 'PASS_TO_PASS' {
                Assert-Equal $invalidRun.Count $invalidInputs.Count 'Invalid inputs must not change the result count.'
                foreach ($result in $invalidRun) {
                    Assert-Equal $result.Status 'Failed' 'Empty, directory, wildcard, and missing paths must fail independently.'
                }
            }

            $adsInput = $markedPath + ':AuditTag'
            $adsRun = @(Invoke-CleanerSafely -Inputs $adsInput)
            Add-Check -Id 'PASS-05-ads-input-rejected' -Category 'PASS_TO_PASS' {
                Assert-Equal $adsRun.Count 1 'An ADS input must return one result.'
                Assert-Equal $adsRun[0].Status 'Failed' 'An alternate data stream must not be treated as a regular file.'
                Assert-True ((Get-NamedStreamText -Path $markedPath -StreamName 'AuditTag') -ne $null) 'Rejecting an ADS input must not delete the stream.'
            }

            $reparseTarget = Join-Path $tempRoot 'reparse-target'
            $junctionPath = Join-Path $fixtureDir 'junction'
            New-Item -ItemType Directory -Force -Path $reparseTarget | Out-Null
            New-Item -ItemType Junction -Path $junctionPath -Target $reparseTarget | Out-Null
            $junctionRun = @(Invoke-CleanerSafely -Inputs $junctionPath)
            Add-Check -Id 'PASS-06-reparse-rejected' -Category 'PASS_TO_PASS' {
                Assert-Equal $junctionRun.Count 1 'A reparse-point input must return one result.'
                Assert-Equal $junctionRun[0].Status 'Failed' 'Junctions and other reparse points must be rejected.'
            }

            $contractInputs = @($casePath, '', $missingPath)
            $contractRun = @(Invoke-CleanerSafely -Inputs $contractInputs)
            Add-Check -Id 'PASS-07-result-contract' -Category 'PASS_TO_PASS' {
                Assert-ResultContract -Results $contractRun -Inputs $contractInputs
            }

            $relativeFile = Join-Path $fixtureDir 'relative-input.txt'
            [System.IO.File]::WriteAllText($relativeFile, 'relative-content', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $relativeFile -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $relativeInput = '.\' + ([char]0x76EE) + ([char]0x5F55) + ' with spaces\relative-input.txt'
            Push-Location $tempRoot
            try {
                $relativeRun = @(Invoke-CleanerSafely -Inputs $relativeInput)
            }
            finally {
                Pop-Location
            }
            Add-Check -Id 'PASS-08-relative-path-echo' -Category 'PASS_TO_PASS' {
                Assert-Equal $relativeRun.Count 1 'A relative input must return one result.'
                Assert-Equal $relativeRun[0].Status 'Removed' 'The relative regular file must be cleaned.'
                Assert-Equal $relativeRun[0].Path $relativeInput 'Path must echo the relative input exactly.'
                Assert-True ([string]::IsNullOrEmpty([string]$relativeRun[0].Error)) 'A successful relative-path result must have an empty Error.'
            }

            $previewPath = Join-Path $fixtureDir 'preview.txt'
            [System.IO.File]::WriteAllText($previewPath, 'preview-content', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $previewPath -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $previewBefore = Get-FileSnapshot -Path $previewPath
            $previewAudit = Join-Path $fixtureDir 'preview.jsonl'
            $previewRun = @(Invoke-CleanerWithOptions -Inputs $previewPath -WhatIf -AuditPath $previewAudit)
            Add-Check -Id 'F2P-14-whatif-status' -Category 'FAIL_TO_PASS' {
                Assert-Equal $previewRun.Count 1 'WhatIf must return one result.'
                Assert-Equal $previewRun[0].Status 'WouldRemove' 'WhatIf must report WouldRemove for a marked file.'
            }
            Add-Check -Id 'F2P-15-whatif-no-mutation' -Category 'FAIL_TO_PASS' {
                $after = Get-FileSnapshot -Path $previewPath
                Assert-Equal ((Get-NamedStreamText -Path $previewPath -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'WhatIf removed or changed the target stream.'
                Assert-Equal $after.Hash $previewBefore.Hash 'WhatIf changed the primary file.'
                Assert-True (-not (Test-Path -LiteralPath $previewAudit)) 'WhatIf created an audit file.'
            }

            # Instruction clause 6: -WhatIf still validates each input, returns Failed for
            # rejected paths, AlreadyClean for an unmarked file and WouldRemove for a marked one.
            $whatifInvalidMissing = Join-Path $fixtureDir 'whatif-invalid-missing.txt'
            $whatifInvalidDir = Join-Path $fixtureDir 'whatif-invalid-dir'
            New-Item -ItemType Directory -Force -Path $whatifInvalidDir | Out-Null
            $whatifInvalidMarked = Join-Path $fixtureDir 'whatif-invalid-marked.txt'
            [System.IO.File]::WriteAllText($whatifInvalidMarked, 'whatif-invalid-marked', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $whatifInvalidMarked -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $whatifInvalidClean = Join-Path $fixtureDir 'whatif-invalid-clean.txt'
            [System.IO.File]::WriteAllText($whatifInvalidClean, 'whatif-invalid-clean', (New-Object System.Text.UTF8Encoding($false)))
            $whatifInvalidMarkedBefore = Get-FileSnapshot -Path $whatifInvalidMarked
            $whatifInvalidCleanBefore = Get-FileSnapshot -Path $whatifInvalidClean
            $whatifInvalidInputs = @($whatifInvalidMissing, $whatifInvalidDir, '', $whatifInvalidMarked, $whatifInvalidClean)
            $whatifInvalidRun = @(Invoke-CleanerWithOptions -Inputs $whatifInvalidInputs -WhatIf)
            $whatifInvalidMarkedAfter = Get-FileSnapshot -Path $whatifInvalidMarked
            $whatifInvalidCleanAfter = Get-FileSnapshot -Path $whatifInvalidClean
            Add-Check -Id 'F2P-28-whatif-input-states' -Category 'FAIL_TO_PASS' {
                Assert-Equal $whatifInvalidRun.Count 5 'A WhatIf batch must return one result per input.'
                foreach ($invalidIndex in @(0, 1, 2)) {
                    Assert-Equal $whatifInvalidRun[$invalidIndex].Status 'Failed' 'WhatIf must still reject invalid inputs.'
                    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$whatifInvalidRun[$invalidIndex].Error)) 'A WhatIf rejection needs a readable Error.'
                }
                Assert-Equal $whatifInvalidRun[3].Status 'WouldRemove' 'WhatIf must preview a marked file as WouldRemove.'
                Assert-Equal $whatifInvalidRun[4].Status 'AlreadyClean' 'WhatIf must report an unmarked file as AlreadyClean.'
                Assert-True ([string]::IsNullOrEmpty([string]$whatifInvalidRun[3].Error)) 'A WhatIf preview result must have an empty Error.'
                Assert-Equal ((Get-NamedStreamText -Path $whatifInvalidMarked -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'WhatIf removed the target stream.'
                Assert-Equal $whatifInvalidMarkedAfter.Hash $whatifInvalidMarkedBefore.Hash 'WhatIf changed the marked primary file.'
                Assert-Equal $whatifInvalidCleanAfter.Hash $whatifInvalidCleanBefore.Hash 'WhatIf changed the clean primary file.'
            }

            $atomicFirst = Join-Path $fixtureDir 'atomic-first.txt'
            $atomicSecond = Join-Path $fixtureDir 'atomic-second.txt'
            [System.IO.File]::WriteAllText($atomicFirst, 'atomic-first', (New-Object System.Text.UTF8Encoding($false)))
            [System.IO.File]::WriteAllText($atomicSecond, 'atomic-second', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $atomicFirst -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-Content -LiteralPath $atomicSecond -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $atomicMissing = Join-Path $fixtureDir 'atomic-missing.txt'
            $atomicAudit = Join-Path $fixtureDir 'atomic-cancel.jsonl'
            $atomicCancel = @(Invoke-CleanerWithOptions -Inputs @($atomicFirst, $atomicMissing, $atomicSecond) -Atomic -AuditPath $atomicAudit)
            Add-Check -Id 'F2P-16-atomic-preflight' -Category 'FAIL_TO_PASS' {
                Assert-Equal $atomicCancel.Count 3 'Atomic cancellation must return one result per input.'
                foreach ($result in $atomicCancel) {
                    Assert-Equal $result.Status 'Failed' 'An invalid atomic batch must fail every input.'
                    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$result.Error)) 'Atomic cancellation must be explained as a batch cancellation or preflight failure.'
                }
            }
            Add-Check -Id 'F2P-17-atomic-no-partial-mutation' -Category 'FAIL_TO_PASS' {
                Assert-Equal ((Get-NamedStreamText -Path $atomicFirst -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'Atomic preflight failure changed the first file.'
                Assert-Equal ((Get-NamedStreamText -Path $atomicSecond -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'Atomic preflight failure changed the second file.'
                Assert-True (-not (Test-Path -LiteralPath $atomicAudit)) 'Atomic preflight failure created an audit file.'
            }

            # A fresh success fixture must not inherit damage from a prior failed candidate call.
            $atomicFirst = Join-Path $fixtureDir 'atomic-success-marked.txt'
            [IO.File]::WriteAllBytes($atomicFirst, [byte[]]@(0,255,13,10,32,65,0,90))
            Set-AtomicFixtureStream -Path $atomicFirst -Name 'Zone.Identifier' -Bytes ([byte[]]@(90,111,110,101,73,100,61,51))
            Set-AtomicFixtureStream -Path $atomicFirst -Name 'Keep' -Bytes ([byte[]]@(0,255,32,13,10,65,97,0))
            Set-AtomicFixtureStream -Path $atomicFirst -Name 'Zone.Identifier.bak' -Bytes ([byte[]]@(32,66,97,99,107,117,112,32))
            Set-FixtureTimes -Path $atomicFirst -Seed ([datetime]'2020-01-02T03:04:05Z')
            $atomicClean = Join-Path $fixtureDir 'atomic-clean.txt'
            [System.IO.File]::WriteAllText($atomicClean, 'already-clean', (New-Object System.Text.UTF8Encoding($false)))
            Set-AtomicFixtureStream -Path $atomicClean -Name 'Keep' -Bytes ([byte[]]@(255,0,32,13,10))
            Set-FixtureTimes -Path $atomicClean -Seed ([datetime]'2020-02-03T04:05:06Z')
            $atomicFirstBefore = Get-AtomicSuccessState -Path $atomicFirst
            $atomicCleanBefore = Get-AtomicSuccessState -Path $atomicClean
            $atomicCommitAudit = Join-Path $fixtureDir 'atomic-commit.jsonl'
            $atomicCommit = @(Invoke-CleanerWithOptions -Inputs @($atomicFirst, $atomicClean) -Atomic -AuditPath $atomicCommitAudit)
            Add-Check -Id 'F2P-18-atomic-commit-order' -Category 'FAIL_TO_PASS' {
                Assert-Equal $atomicCommit.Count 2 'Atomic commit must preserve result count.'
                Assert-Equal $atomicCommit[0].Status 'Removed' 'Atomic commit did not remove the marked first file.'
                Assert-Equal $atomicCommit[1].Status 'AlreadyClean' 'Atomic commit misreported a clean file.'
                Assert-AtomicSuccessState -Path $atomicFirst -Before $atomicFirstBefore
                Assert-AtomicSuccessState -Path $atomicClean -Before $atomicCleanBefore
            }
            Add-Check -Id 'F2P-19-atomic-audit' -Category 'FAIL_TO_PASS' {
                # A mutually consistent result and audit still need a real committed state.
                Assert-AtomicSuccessState -Path $atomicFirst -Before $atomicFirstBefore
                Assert-AtomicSuccessState -Path $atomicClean -Before $atomicCleanBefore
                Assert-True (Test-Path -LiteralPath $atomicCommitAudit -PathType Leaf) 'Atomic commit did not create the audit file.'
                $auditLines = @(Get-Content -LiteralPath $atomicCommitAudit -Encoding UTF8 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
                Assert-Equal $auditLines.Count 2 'Audit output must contain one JSON line per input.'
                $audit = @($auditLines | ForEach-Object { $_ | ConvertFrom-Json })
                Assert-Equal $audit[0].Path $atomicFirst 'Audit path order is incorrect.'
                Assert-Equal $audit[0].Status 'Removed' 'Audit status does not match the result.'
                Assert-Equal $audit[1].Path $atomicClean 'Audit did not include the clean input.'
                for ($auditIndex = 0; $auditIndex -lt $audit.Count; $auditIndex++) {
                    $entry = $audit[$auditIndex]
                    $expectedResult = $atomicCommit[$auditIndex]
                    foreach ($field in @('Path', 'Status', 'Error', 'TimestampUtc')) {
                        Assert-True ($entry.PSObject.Properties.Name -contains $field) ('Audit entry lacks ' + $field)
                    }
                    Assert-Equal $entry.Path $expectedResult.Path 'Audit path does not match result.'
                    Assert-Equal $entry.Status $expectedResult.Status 'Audit status does not match result.'
                    Assert-Equal $entry.Error $expectedResult.Error 'Audit error does not match result.'
                    $timestamp = [DateTimeOffset]::MinValue
                    $timestampText = if ($entry.TimestampUtc -is [DateTime]) { $entry.TimestampUtc.ToString('o') } else { [string]$entry.TimestampUtc }
                    $timestampValid = [DateTimeOffset]::TryParse($timestampText, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$timestamp)
                    $timestampValid = $timestampValid -and ($timestampText -match '(Z|[+]00:00)$')
                    Assert-True ($timestampValid -and $timestamp.Offset -eq [TimeSpan]::Zero) 'TimestampUtc must be parseable UTC.'
                }
            }

            $badAuditDir = Join-Path $fixtureDir 'bad-audit-target'
            New-Item -ItemType Directory -Force -Path $badAuditDir | Out-Null
            $badAuditFile = Join-Path $fixtureDir 'bad-audit-input.txt'
            [System.IO.File]::WriteAllText($badAuditFile, 'bad-audit', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $badAuditFile -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $badAuditRun = @(Invoke-CleanerWithOptions -Inputs $badAuditFile -Atomic -AuditPath $badAuditDir)
            Add-Check -Id 'F2P-20-audit-preflight' -Category 'FAIL_TO_PASS' {
                Assert-Equal $badAuditRun.Count 1 'Invalid audit target must return one result.'
                Assert-Equal $badAuditRun[0].Status 'Failed' 'A directory audit target must fail before commit.'
                Assert-Equal ((Get-NamedStreamText -Path $badAuditFile -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'Invalid audit target allowed file mutation.'
            }

            # Instruction clause 9: audit output is appended, one JSON line per input, and a
            # repeated audited call must not truncate the evidence written by the earlier call.
            $appendAuditInput = Join-Path $fixtureDir 'append-audit.txt'
            [System.IO.File]::WriteAllText($appendAuditInput, 'append-audit', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $appendAuditInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $appendAuditPath = Join-Path $fixtureDir 'append-audit.jsonl'
            $appendFirstRun = @(Invoke-CleanerWithOptions -Inputs $appendAuditInput -AuditPath $appendAuditPath)
            $appendSecondRun = @(Invoke-CleanerWithOptions -Inputs $appendAuditInput -AuditPath $appendAuditPath)
            Add-Check -Id 'F2P-23-audit-appends-per-call' -Category 'FAIL_TO_PASS' {
                Assert-Equal $appendFirstRun.Count 1 'The first audited call must return one result.'
                Assert-Equal $appendFirstRun[0].Status 'Removed' 'The first audited call must remove the mark.'
                Assert-Equal $appendSecondRun.Count 1 'The second audited call must return one result.'
                Assert-Equal $appendSecondRun[0].Status 'AlreadyClean' 'The repeated audited call must observe the committed state.'
                Assert-True (Test-Path -LiteralPath $appendAuditPath -PathType Leaf) 'The audited call did not create the audit file.'
                Assert-True ((Get-NamedStreamText -Path $appendAuditInput -StreamName 'Zone.Identifier') -eq $null) 'The audited call did not remove the mark.'
                $appendLines = @(Get-Content -LiteralPath $appendAuditPath -Encoding UTF8 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
                Assert-Equal $appendLines.Count 2 'Audit output must be appended, one JSON line per call.'
                $appendEntries = @($appendLines | ForEach-Object { $_ | ConvertFrom-Json })
                Assert-Equal $appendEntries[0].Path $appendAuditInput 'The first audit entry path is wrong.'
                Assert-Equal $appendEntries[1].Path $appendAuditInput 'The appended audit entry path is wrong.'
                Assert-Equal $appendEntries[0].Status 'Removed' 'The first audit entry must describe the removal.'
                Assert-Equal $appendEntries[1].Status 'AlreadyClean' 'The appended audit entry must describe the clean state.'
            }

            # Instruction clause 8: an audit target that is an alternate data stream must be
            # rejected before any deletion, and that stream must not be created as a side effect.
            $adsAuditInput = Join-Path $fixtureDir 'ads-audit-input.txt'
            [System.IO.File]::WriteAllText($adsAuditInput, 'ads-audit-input', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $adsAuditInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $adsAuditRun = @(Invoke-CleanerWithOptions -Inputs $adsAuditInput -Atomic -AuditPath ($adsAuditInput + ':AuditStream'))
            Add-Check -Id 'F2P-24-audit-target-ads-rejected' -Category 'FAIL_TO_PASS' {
                Assert-Equal $adsAuditRun.Count 1 'An ADS audit target must return one result.'
                Assert-Equal $adsAuditRun[0].Status 'Failed' 'An alternate-data-stream audit target must fail preflight.'
                Assert-True (-not [string]::IsNullOrWhiteSpace([string]$adsAuditRun[0].Error)) 'A rejected audit target needs a readable Error.'
                Assert-Equal ((Get-NamedStreamText -Path $adsAuditInput -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'A rejected ADS audit target allowed file mutation.'
                Assert-True ((Get-NamedStreamText -Path $adsAuditInput -StreamName 'AuditStream') -eq $null) 'The rejected audit stream was created anyway.'
            }

            # Instruction clause 8: a wildcard audit target must be rejected before deletion and
            # must not be created literally either.
            $wcAuditInput = Join-Path $fixtureDir 'wc-audit-input.txt'
            [System.IO.File]::WriteAllText($wcAuditInput, 'wc-audit-input', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $wcAuditInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $wildcardAuditTarget = Join-Path $fixtureDir 'wildcard-audit-*.jsonl'
            $wildcardAuditRun = @(Invoke-CleanerWithOptions -Inputs $wcAuditInput -Atomic -AuditPath $wildcardAuditTarget)
            Add-Check -Id 'F2P-25-audit-target-wildcard-rejected' -Category 'FAIL_TO_PASS' {
                Assert-Equal $wildcardAuditRun.Count 1 'A wildcard audit target must return one result.'
                Assert-Equal $wildcardAuditRun[0].Status 'Failed' 'A wildcard audit target must fail preflight.'
                Assert-True (-not [string]::IsNullOrWhiteSpace([string]$wildcardAuditRun[0].Error)) 'A rejected audit target needs a readable Error.'
                Assert-Equal ((Get-NamedStreamText -Path $wcAuditInput -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'A rejected wildcard audit target allowed file mutation.'
                $wildcardLeftovers = @(Get-ChildItem -LiteralPath $fixtureDir | Where-Object { $_.Name -like 'wildcard-audit-*' })
                Assert-Equal $wildcardLeftovers.Count 0 'The rejected wildcard audit target was created anyway.'
            }

            $rollbackFirst = Join-Path $fixtureDir 'rollback-first.txt'
            $rollbackSecond = Join-Path $fixtureDir 'rollback-second.txt'
            $lockedAudit = Join-Path $fixtureDir 'locked-audit.jsonl'
            [System.IO.File]::WriteAllText($rollbackFirst, 'rollback-first', (New-Object System.Text.UTF8Encoding($false)))
            [System.IO.File]::WriteAllText($rollbackSecond, 'rollback-second', (New-Object System.Text.UTF8Encoding($false)))
            [System.IO.File]::WriteAllText($lockedAudit, '', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $rollbackFirst -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-Content -LiteralPath $rollbackSecond -Stream 'Zone.Identifier' -Value 'ZoneId=4' -Encoding UTF8
            $rollbackFirstBefore = Get-FileSnapshot -Path $rollbackFirst
            $rollbackSecondBefore = Get-FileSnapshot -Path $rollbackSecond
            # Lock exists before invocation: this proves no mutation on audit failure,
            # not that a mutation occurred and was subsequently rolled back.
            $auditLock = [System.IO.File]::Open($lockedAudit, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            try {
                $rollbackRun = @(Invoke-CleanerWithOptions -Inputs @($rollbackFirst, $rollbackSecond) -Atomic -AuditPath $lockedAudit)
            }
            finally {
                $auditLock.Dispose()
            }
            Add-Check -Id 'F2P-21-locked-audit-no-mutation' -Category 'FAIL_TO_PASS' {
                Assert-Equal $rollbackRun.Count 2 'A failed atomic commit must return one result per input.'
                foreach ($result in $rollbackRun) { Assert-Equal $result.Status 'Failed' 'A failed atomic commit must fail the whole batch.' }
                Assert-Equal ((Get-NamedStreamText -Path $rollbackFirst -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'The first stream was not restored after commit failure.'
                Assert-Equal ((Get-NamedStreamText -Path $rollbackSecond -StreamName 'Zone.Identifier').Trim()) 'ZoneId=4' 'The second stream was not restored after commit failure.'
                $rollbackFirstAfter = Get-FileSnapshot -Path $rollbackFirst
                $rollbackSecondAfter = Get-FileSnapshot -Path $rollbackSecond
                Assert-Equal $rollbackFirstAfter.Hash $rollbackFirstBefore.Hash 'The first primary file changed during rollback.'
                Assert-Equal $rollbackSecondAfter.Hash $rollbackSecondBefore.Hash 'The second primary file changed during rollback.'
            }

            . (Join-Path $PSScriptRoot 'atomic_commit_probe.ps1')
            $commitProbe = Invoke-AtomicCommitProbe -FixtureDir $fixtureDir
            $commitProbe | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path (Split-Path -Parent $OutputPath) 'atomic-commit-evidence.json') -Encoding UTF8
            Add-Check -Id 'F2P-22-atomic-delete-failure' -Category 'FAIL_TO_PASS' {
                Assert-True $commitProbe.passed 'Atomic deletion failure must fail the batch and preserve primary files, streams, attributes and times.'
            }

            # Instruction clauses 6+7: -Atomic and -WhatIf together are still a preview: nothing
            # is committed and no audit output is created.
            $atomicPreviewPath = Join-Path $fixtureDir 'atomic-preview.txt'
            [System.IO.File]::WriteAllText($atomicPreviewPath, 'atomic-preview', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $atomicPreviewPath -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $atomicPreviewBefore = Get-FileSnapshot -Path $atomicPreviewPath
            $atomicPreviewAudit = Join-Path $fixtureDir 'atomic-preview.jsonl'
            $atomicPreviewRun = @(Invoke-CleanerWithOptions -Inputs $atomicPreviewPath -Atomic -WhatIf -AuditPath $atomicPreviewAudit)
            $atomicPreviewAfter = Get-FileSnapshot -Path $atomicPreviewPath
            Add-Check -Id 'F2P-27-atomic-whatif-preview' -Category 'FAIL_TO_PASS' {
                Assert-Equal $atomicPreviewRun.Count 1 'Atomic WhatIf must return one result.'
                Assert-Equal $atomicPreviewRun[0].Status 'WouldRemove' 'Atomic WhatIf must report WouldRemove.'
                Assert-Equal ((Get-NamedStreamText -Path $atomicPreviewPath -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'Atomic WhatIf removed the target stream.'
                Assert-Equal $atomicPreviewAfter.Hash $atomicPreviewBefore.Hash 'Atomic WhatIf changed the primary file.'
                Assert-True (-not (Test-Path -LiteralPath $atomicPreviewAudit)) 'Atomic WhatIf created an audit file.'
            }

            # Instruction clauses 1/5/9: normal-mode audit writes one ordered line per input,
            # including Failed entries, and a rejected input must not stop later work.
            $mixedAuditMissing = Join-Path $fixtureDir 'mixed-audit-missing.txt'
            $mixedAuditMarked = Join-Path $fixtureDir 'mixed-audit-marked.txt'
            [System.IO.File]::WriteAllText($mixedAuditMarked, 'mixed-audit', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $mixedAuditMarked -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $mixedAuditPath = Join-Path $fixtureDir 'mixed-audit.jsonl'
            $mixedAuditRun = @(Invoke-CleanerWithOptions -Inputs @($mixedAuditMissing, $mixedAuditMarked) -AuditPath $mixedAuditPath)
            Add-Check -Id 'F2P-26-mixed-audit-order' -Category 'FAIL_TO_PASS' {
                Assert-Equal $mixedAuditRun.Count 2 'A mixed audited batch must return one result per input.'
                Assert-Equal $mixedAuditRun[0].Path $mixedAuditMissing 'Mixed audit result order changed.'
                Assert-Equal $mixedAuditRun[1].Path $mixedAuditMarked 'Mixed audit result order changed.'
                Assert-Equal $mixedAuditRun[0].Status 'Failed' 'The missing input must be Failed.'
                Assert-Equal $mixedAuditRun[1].Status 'Removed' 'The marked input must be removed.'
                Assert-True ((Get-NamedStreamText -Path $mixedAuditMarked -StreamName 'Zone.Identifier') -eq $null) 'The valid input after a failure was not cleaned.'
                $mixedAuditLines = @(Get-Content -LiteralPath $mixedAuditPath -Encoding UTF8 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
                Assert-Equal $mixedAuditLines.Count 2 'Mixed audit output must contain one line per input.'
                $mixedAuditEntries = @($mixedAuditLines | ForEach-Object { $_ | ConvertFrom-Json })
                Assert-Equal $mixedAuditEntries[0].Path $mixedAuditMissing 'First mixed audit path is out of order.'
                Assert-Equal $mixedAuditEntries[1].Path $mixedAuditMarked 'Second mixed audit path is out of order.'
                Assert-Equal $mixedAuditEntries[0].Status 'Failed' 'The failed input must be audited as Failed.'
                Assert-True (-not [string]::IsNullOrWhiteSpace([string]$mixedAuditEntries[0].Error)) 'The failed audit entry needs a readable Error.'
                Assert-Equal $mixedAuditEntries[1].Status 'Removed' 'Marked mixed input was not removed.'
            }

            $atomicDuplicate = Join-Path $fixtureDir 'atomic-duplicate.txt'
            [System.IO.File]::WriteAllText($atomicDuplicate, 'atomic-duplicate', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $atomicDuplicate -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-AtomicFixtureStream -Path $atomicDuplicate -Name 'Keep' -Bytes ([byte[]]@(0,255,32,13,10,65,97))
            Set-FixtureTimes -Path $atomicDuplicate -Seed ([datetime]'2020-03-04T05:06:07Z')
            $atomicDuplicateBefore = Get-AtomicSuccessState -Path $atomicDuplicate
            $atomicDuplicateRun = @(Invoke-CleanerWithOptions -Inputs @($atomicDuplicate, $atomicDuplicate) -Atomic)
            Add-Check -Id 'PASS-09-atomic-duplicate-order' -Category 'PASS_TO_PASS' {
                Assert-Equal $atomicDuplicateRun.Count 2 'Atomic duplicate inputs must produce two results.'
                Assert-Equal $atomicDuplicateRun[0].Status 'Removed' 'The first atomic duplicate must remove the stream.'
                Assert-Equal $atomicDuplicateRun[1].Status 'AlreadyClean' 'The second atomic duplicate must observe the committed state.'
                Assert-AtomicSuccessState -Path $atomicDuplicate -Before $atomicDuplicateBefore
            }

            # Instruction clauses 10-12: the parent chain and the real file identity, not just
            # the leaf path string, decide validity and audit-target conflicts.
            $junctionLinkRoot = Join-Path $fixtureDir 'junction-root'
            $junctionRealRoot = Join-Path $fixtureDir 'junction-real'
            New-Item -ItemType Directory -Force -Path $junctionLinkRoot | Out-Null
            New-Item -ItemType Directory -Force -Path $junctionRealRoot | Out-Null
            $junctionLink = Join-Path $junctionLinkRoot 'link'
            New-Item -ItemType Junction -Path $junctionLink -Target $junctionRealRoot -ErrorAction Stop | Out-Null

            $junctionInput = Join-Path $junctionRealRoot 'through-junction.txt'
            [System.IO.File]::WriteAllText($junctionInput, 'junction-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $junctionInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-Content -LiteralPath $junctionInput -Stream 'Keep' -Value 'junction-keep' -Encoding UTF8
            $junctionBefore = Get-FileSnapshot -Path $junctionInput
            $junctionRun = @(Invoke-CleanerWithOptions -Inputs (Join-Path $junctionLink 'through-junction.txt'))
            Add-Check -Id 'F2P-29-parent-reparse-rejected' -Category 'FAIL_TO_PASS' {
                Assert-Equal $junctionRun.Count 1 'A junction-traversing input must return one result.'
                Assert-Equal $junctionRun[0].Status 'Failed' 'A parent-chain reparse point must reject the input.'
                Assert-True (-not [string]::IsNullOrWhiteSpace([string]$junctionRun[0].Error)) 'The rejected junction input needs a readable Error.'
                Assert-Equal ([string](Get-NamedStreamText -Path $junctionInput -StreamName 'Zone.Identifier')).Trim() 'ZoneId=3' 'The rejected junction input must keep its source mark.'
                Assert-Equal ([string](Get-NamedStreamText -Path $junctionInput -StreamName 'Keep')).Trim() 'junction-keep' 'The rejected junction input must keep unrelated streams.'
                Assert-Equal (Get-FileSnapshot -Path $junctionInput).Hash $junctionBefore.Hash 'The rejected junction input must not change the primary file.'
            }

            $auditJunctionInput = Join-Path $fixtureDir 'audit-junction-input.txt'
            [System.IO.File]::WriteAllText($auditJunctionInput, 'audit-junction', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $auditJunctionInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $auditJunctionBefore = Get-FileSnapshot -Path $auditJunctionInput
            $auditJunctionProbe = Join-Path $junctionRealRoot 'audit-through-junction.jsonl'
            $auditJunctionRun = @(Invoke-CleanerWithOptions -Inputs $auditJunctionInput -AuditPath (Join-Path $junctionLink 'audit-through-junction.jsonl'))
            Add-Check -Id 'F2P-30-audit-parent-reparse-rejected' -Category 'FAIL_TO_PASS' {
                Assert-Equal $auditJunctionRun.Count 1 'A rejected audit parent must still return one result per input.'
                Assert-Equal $auditJunctionRun[0].Status 'Failed' 'An AuditPath under a reparse-point parent must be rejected before deletion.'
                Assert-True (-not (Test-Path -LiteralPath $auditJunctionProbe)) 'The rejected audit target must not be created.'
                Assert-Equal ([string](Get-NamedStreamText -Path $auditJunctionInput -StreamName 'Zone.Identifier')).Trim() 'ZoneId=3' 'A rejected audit target must not delete the source mark.'
                Assert-Equal (Get-FileSnapshot -Path $auditJunctionInput).Hash $auditJunctionBefore.Hash 'A rejected audit target must not change the input file.'
            }

            $identityInput = Join-Path $fixtureDir 'identity-input.txt'
            [System.IO.File]::WriteAllText($identityInput, 'identity-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $identityInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $identityAuditLink = Join-Path $fixtureDir 'identity-audit-link.jsonl'
            New-Item -ItemType HardLink -Path $identityAuditLink -Target $identityInput -ErrorAction Stop | Out-Null
            $identityBefore = Get-FileSnapshot -Path $identityInput
            $identityRun = @(Invoke-CleanerWithOptions -Inputs $identityInput -AuditPath $identityAuditLink)
            Add-Check -Id 'F2P-31-audit-input-identity-collision' -Category 'FAIL_TO_PASS' {
                Assert-Equal $identityRun.Count 1 'An audit identity conflict must still return one result per input.'
                Assert-Equal $identityRun[0].Status 'Failed' 'An AuditPath that is the same file object as an input must be rejected.'
                Assert-Equal ([string](Get-NamedStreamText -Path $identityInput -StreamName 'Zone.Identifier')).Trim() 'ZoneId=3' 'The audit identity conflict must fail before any deletion.'
                Assert-Equal (Get-FileSnapshot -Path $identityInput).Hash $identityBefore.Hash 'The audit identity conflict must not touch the input file.'
            }

            $duplicateLinkA = Join-Path $fixtureDir 'duplicate-identity-a.txt'
            $duplicateLinkB = Join-Path $fixtureDir 'duplicate-identity-b.txt'
            [System.IO.File]::WriteAllText($duplicateLinkA, 'duplicate-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $duplicateLinkA -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            New-Item -ItemType HardLink -Path $duplicateLinkB -Target $duplicateLinkA -ErrorAction Stop | Out-Null
            $duplicateLinkBefore = Get-FileSnapshot -Path $duplicateLinkA
            $duplicateLinkRun = @(Invoke-CleanerWithOptions -Inputs @($duplicateLinkA, $duplicateLinkB) -Atomic)
            Add-Check -Id 'F2P-32-hardlink-duplicate-identity' -Category 'FAIL_TO_PASS' {
                Assert-Equal $duplicateLinkRun.Count 2 'A hard-link duplicate batch must produce two results.'
                Assert-Equal $duplicateLinkRun[0].Path $duplicateLinkA 'The first hard-link reference must echo its own literal path.'
                Assert-Equal $duplicateLinkRun[1].Path $duplicateLinkB 'The second hard-link reference must echo its own literal path.'
                Assert-Equal $duplicateLinkRun[0].Status 'Removed' 'The first hard-link reference must report Removed.'
                Assert-Equal $duplicateLinkRun[1].Status 'AlreadyClean' 'The second hard-link reference must observe the committed state.'
                Assert-True ((Get-NamedStreamText -Path $duplicateLinkB -StreamName 'Zone.Identifier') -eq $null) 'The shared source mark must be gone through both links.'
                Assert-Equal (Get-FileSnapshot -Path $duplicateLinkA).Hash $duplicateLinkBefore.Hash 'Hard-link identity handling must not change the primary content.'
                Assert-Equal (Get-FileSnapshot -Path $duplicateLinkA).Identity $duplicateLinkBefore.Identity 'Hard-link identity handling must not replace the file object.'
            }

            # Instruction clauses 13-14: the audit target must be provably writable before any
            # deletion, and a junction-parent path invalidates a batch even when the very same
            # file object is also reachable through a valid hard link.
            $denyDir = Join-Path $fixtureDir 'deny-write'
            New-Item -ItemType Directory -Force -Path $denyDir | Out-Null
            $denyInput = Join-Path $fixtureDir 'deny-write-input.txt'
            [System.IO.File]::WriteAllText($denyInput, 'deny-write-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $denyInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $denyBefore = Get-FileSnapshot -Path $denyInput
            $denyAudit = Join-Path $denyDir 'audit.jsonl'
            $denyUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $denyAcl = Get-Acl -LiteralPath $denyDir
            $denyRule = New-Object System.Security.AccessControl.FileSystemAccessRule($denyUser, 'Write,CreateFiles', 'Deny')
            [void]$denyAcl.AddAccessRule($denyRule)
            Set-Acl -LiteralPath $denyDir -AclObject $denyAcl
            try {
                $denyRun = @(Invoke-CleanerWithOptions -Inputs $denyInput -AuditPath $denyAudit)
            }
            finally {
                $denyRestore = Get-Acl -LiteralPath $denyDir
                [void]$denyRestore.RemoveAccessRule($denyRule)
                Set-Acl -LiteralPath $denyDir -AclObject $denyRestore
            }
            Add-Check -Id 'F2P-33-audit-parent-deny-write' -Category 'FAIL_TO_PASS' {
                Assert-Equal $denyRun.Count 1 'A rejected audit parent must still return one result per input.'
                Assert-Equal $denyRun[0].Status 'Failed' 'An unwritable audit parent must fail before deletion.'
                Assert-True (-not (Test-Path -LiteralPath $denyAudit)) 'The audit file must not be created in an unwritable parent.'
                Assert-Equal ([string](Get-NamedStreamText -Path $denyInput -StreamName 'Zone.Identifier')).Trim() 'ZoneId=3' 'A rejected audit target must not delete the source mark.'
                Assert-Equal (Get-FileSnapshot -Path $denyInput).Hash $denyBefore.Hash 'A rejected audit target must not change the input file.'
            }

            $crossReal = Join-Path $fixtureDir 'cross-real'
            $crossLinkRoot = Join-Path $fixtureDir 'cross-link-root'
            New-Item -ItemType Directory -Force -Path $crossReal | Out-Null
            New-Item -ItemType Directory -Force -Path $crossLinkRoot | Out-Null
            $crossLink = Join-Path $crossLinkRoot 'link'
            New-Item -ItemType Junction -Path $crossLink -Target $crossReal -ErrorAction Stop | Out-Null
            $crossFile = Join-Path $crossReal 'cross.txt'
            [System.IO.File]::WriteAllText($crossFile, 'cross-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $crossFile -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $crossHard = Join-Path $fixtureDir 'cross-hard.txt'
            New-Item -ItemType HardLink -Path $crossHard -Target $crossFile -ErrorAction Stop | Out-Null
            $crossBefore = Get-FileSnapshot -Path $crossFile
            $crossRun = @(Invoke-CleanerWithOptions -Inputs @($crossHard, (Join-Path $crossLink 'cross.txt')) -Atomic)
            Add-Check -Id 'F2P-34-cross-identity-junction-batch' -Category 'FAIL_TO_PASS' {
                Assert-Equal $crossRun.Count 2 'A cross-identity batch must return one result per input.'
                Assert-Equal $crossRun[0].Status 'Failed' 'A junction-parent path must cancel the whole atomic batch.'
                Assert-Equal $crossRun[1].Status 'Failed' 'The junction-parent path itself must be Failed.'
                Assert-Equal ([string](Get-NamedStreamText -Path $crossFile -StreamName 'Zone.Identifier')).Trim() 'ZoneId=3' 'A cancelled batch must keep the shared source mark.'
                Assert-Equal (Get-FileSnapshot -Path $crossFile).Hash $crossBefore.Hash 'A cancelled batch must not change the file.'
            }

            # Instruction clause 8: when an -Atomic commit fails, the rollback outcome of every
            # file must be confirmed individually. A file whose stream was deleted but cannot be
            # written back has to be named as "not restored" instead of disappearing behind a
            # batch-level message, while files that were restored keep their state exactly.
            . (Join-Path $PSScriptRoot 'stream_share_probe.ps1')
            $rollbackDenied = Join-Path $fixtureDir 'rollback-report-denied.txt'
            $rollbackTrigger = Join-Path $fixtureDir 'rollback-report-trigger.txt'
            foreach ($file in @($rollbackDenied, $rollbackTrigger)) {
                [System.IO.File]::WriteAllText($file, 'rollback-report-main', (New-Object System.Text.UTF8Encoding($false)))
                Set-Content -LiteralPath $file -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
                Set-AtomicFixtureStream -Path $file -Name 'Keep' -Bytes ([byte[]]@(0,255,32,13,10,65,97))
            }
            $rollbackDeniedBefore = Get-FileSnapshot -Path $rollbackDenied
            $rollbackDeniedStateBefore = Get-AtomicSuccessState -Path $rollbackDenied
            $rollbackTriggerBefore = Get-FileSnapshot -Path $rollbackTrigger
            $rollbackTriggerStateBefore = Get-AtomicSuccessState -Path $rollbackTrigger
            # A deny data-write entry keeps the first file's stream deletable but makes it
            # impossible to create that stream again, so a rollback cannot restore this file.
            $rollbackUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $rollbackAcl = Get-Acl -LiteralPath $rollbackDenied
            $rollbackDenyRule = New-Object System.Security.AccessControl.FileSystemAccessRule($rollbackUser, 'WriteData', 'Deny')
            [void]$rollbackAcl.AddAccessRule($rollbackDenyRule)
            Set-Acl -LiteralPath $rollbackDenied -AclObject $rollbackAcl
            # The second file's stream is held with a share mode that allows reading and writing
            # but forbids deletion, so its removal fails inside the commit and forces a rollback.
            $rollbackHandle = $null
            try {
                $rollbackHandle = Lock-AdsStreamHandle -StreamPath ($rollbackTrigger + ':Zone.Identifier') -ShareMode 3
                $rollbackReportRun = @(Invoke-CleanerWithOptions -Inputs @($rollbackDenied, $rollbackTrigger) -Atomic)
            }
            finally {
                if ($null -ne $rollbackHandle) { $rollbackHandle.Dispose() }
                $rollbackAclReset = Get-Acl -LiteralPath $rollbackDenied
                [void]$rollbackAclReset.RemoveAccessRule($rollbackDenyRule)
                Set-Acl -LiteralPath $rollbackDenied -AclObject $rollbackAclReset
            }
            Add-Check -Id 'F2P-35-rollback-report' -Category 'FAIL_TO_PASS' {
                Assert-Equal $rollbackReportRun.Count 2 'A failed atomic rollback must return one result per input.'
                foreach ($result in $rollbackReportRun) {
                    Assert-Equal $result.Status 'Failed' 'A batch that cannot fully roll back must fail as a whole.'
                    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$result.Error)) 'A failed rollback needs a readable Error.'
                }
                # The blocked file was never removed, so it must still be intact.
                Assert-Equal ([string](Get-NamedStreamText -Path $rollbackTrigger -StreamName 'Zone.Identifier')).Trim() 'ZoneId=3' 'A file whose removal failed must keep its source mark.'
                $rollbackTriggerStateAfter = Get-AtomicSuccessState -Path $rollbackTrigger
                foreach ($field in @('Hash','Length','Attributes','Identity')) {
                    Assert-True ($rollbackTriggerStateAfter.File.$field -ceq $rollbackTriggerStateBefore.File.$field) ('A failed batch changed the blocked file ' + $field)
                }
                Assert-Equal $rollbackTriggerStateAfter.Streams['Keep'] $rollbackTriggerStateBefore.Streams['Keep'] 'A failed batch changed an unrelated stream of the blocked file.'
                Assert-Equal (Get-FileSnapshot -Path $rollbackTrigger).Hash $rollbackTriggerBefore.Hash 'A failed batch rewrote the blocked file.'
                # If this runtime really deleted the first file's stream, clause 8 requires the
                # batch to name that file as not restored.
                $rollbackDeniedZone = Get-NamedStreamText -Path $rollbackDenied -StreamName 'Zone.Identifier'
                if ($null -eq $rollbackDeniedZone) {
                    $rollbackFailureText = (@($rollbackReportRun | ForEach-Object { [string]$_.Error }) -join [Environment]::NewLine)
                    Assert-True ($rollbackFailureText.IndexOf($rollbackDenied, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) 'A stream that was deleted and could not be restored must be named in the result Error.'
                }
                $rollbackDeniedStateAfter = Get-AtomicSuccessState -Path $rollbackDenied
                foreach ($field in @('Hash','Length','Identity')) {
                    Assert-True ($rollbackDeniedStateAfter.File.$field -ceq $rollbackDeniedStateBefore.File.$field) ('A failed rollback changed the unrestorable file ' + $field)
                }
                Assert-Equal $rollbackDeniedStateAfter.Streams['Keep'] $rollbackDeniedStateBefore.Streams['Keep'] 'A failed rollback changed an unrelated stream of the unrestorable file.'
            }

            # Instruction clause 15: the extended-length spellings are accepted for input paths
            # and for -AuditPath, echoed verbatim, and take the same parent/identity/audit
            # conflict decisions as the equivalent plain spelling.
            $prefixInput = Join-Path $fixtureDir 'prefix-spelling.txt'
            [System.IO.File]::WriteAllText($prefixInput, 'prefix-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $prefixInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-AtomicFixtureStream -Path $prefixInput -Name 'Keep' -Bytes ([byte[]]@(0,255,32,13,10,65,97))
            $prefixStateBefore = Get-AtomicSuccessState -Path $prefixInput
            $prefixSpelling = '\\?\' + (Get-Item -LiteralPath $prefixInput -Force).FullName
            $prefixRun = @(Invoke-CleanerWithOptions -Inputs $prefixSpelling)

            $prefixAuditInput = Join-Path $fixtureDir 'prefix-audit-input.txt'
            [System.IO.File]::WriteAllText($prefixAuditInput, 'prefix-audit-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $prefixAuditInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $prefixAuditFull = (Get-Item -LiteralPath $prefixAuditInput -Force).FullName
            $prefixAuditSpelling = '\\?\' + $prefixAuditFull
            $prefixAuditPlain = Join-Path $fixtureDir 'prefix-audit.jsonl'
            $prefixAuditRun = @(Invoke-CleanerWithOptions -Inputs $prefixAuditSpelling -AuditPath ('\\?\' + $prefixAuditPlain))

            $prefixConflictInput = Join-Path $fixtureDir 'prefix-conflict-input.txt'
            [System.IO.File]::WriteAllText($prefixConflictInput, 'prefix-conflict-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $prefixConflictInput -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            $prefixConflictFull = (Get-Item -LiteralPath $prefixConflictInput -Force).FullName
            $prefixConflictLink = Join-Path $fixtureDir 'prefix-conflict-link.jsonl'
            New-Item -ItemType HardLink -Path $prefixConflictLink -Target $prefixConflictInput -ErrorAction Stop | Out-Null
            $prefixConflictBefore = Get-FileSnapshot -Path $prefixConflictInput
            $prefixConflictRun = @(Invoke-CleanerWithOptions -Inputs ('\\?\' + $prefixConflictFull) -AuditPath $prefixConflictLink)
            Add-Check -Id 'F2P-36-extended-prefix-consistency' -Category 'FAIL_TO_PASS' {
                # The prefixed input is accepted, echoed verbatim and cleaned like the plain form.
                Assert-Equal $prefixRun.Count 1 'A prefixed input must return one result.'
                Assert-Equal $prefixRun[0].Path $prefixSpelling 'The extended-length spelling must be echoed exactly as given.'
                Assert-Equal $prefixRun[0].Status 'Removed' 'An extended-length spelling must be accepted like the plain one.'
                $prefixStateAfter = Get-AtomicSuccessState -Path $prefixInput
                Assert-True (-not $prefixStateAfter.Streams.ContainsKey('Zone.Identifier')) 'The prefixed clean left the source mark on disk.'
                foreach ($field in @('Hash','Length','Attributes','Identity')) {
                    Assert-True ($prefixStateAfter.File.$field -ceq $prefixStateBefore.File.$field) ('The prefixed clean changed primary file ' + $field)
                }
                Assert-Equal $prefixStateAfter.Streams['Keep'] $prefixStateBefore.Streams['Keep'] 'The prefixed clean changed an unrelated stream.'
                # A valid extended-length audit path is accepted and records the prefixed input.
                Assert-Equal $prefixAuditRun.Count 1 'A prefixed audited call must return one result.'
                Assert-Equal $prefixAuditRun[0].Status 'Removed' 'A valid extended-length audit path must be accepted like the plain spelling.'
                Assert-True (Test-Path -LiteralPath $prefixAuditPlain) 'The extended-length audit path did not create the audit file.'
                $prefixAuditEntries = @(Get-Content -LiteralPath $prefixAuditPlain -Encoding UTF8 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_ | ConvertFrom-Json })
                Assert-Equal $prefixAuditEntries.Count 1 'The extended-length audit run must append exactly one line.'
                Assert-Equal ([string]$prefixAuditEntries[0].Path) $prefixAuditSpelling 'The audit line must echo the prefixed input verbatim.'
                Assert-Equal ([string]$prefixAuditEntries[0].Status) 'Removed' 'The audit line must record the removal.'
                # The prefixed spelling must not bypass the audit-target identity conflict.
                Assert-Equal $prefixConflictRun.Count 1 'A prefixed identity conflict must return one result.'
                Assert-Equal $prefixConflictRun[0].Status 'Failed' 'A prefixed input must still detect an audit target that is the same file object.'
                Assert-Equal ([string](Get-NamedStreamText -Path $prefixConflictInput -StreamName 'Zone.Identifier')).Trim() 'ZoneId=3' 'The identity conflict must fail before any deletion.'
                Assert-Equal (Get-FileSnapshot -Path $prefixConflictInput).Hash $prefixConflictBefore.Hash 'The identity conflict must not touch the input file.'
            }

            # Instruction clause 16: cleaning must leave every other piece of file metadata alone.
            # A compressed file carrying an extra access-control entry keeps its compression
            # attribute, its ACL and its owner, and is never rebuilt.
            $metadataFile = Join-Path $fixtureDir 'metadata-preserved.txt'
            [System.IO.File]::WriteAllText($metadataFile, 'metadata-main', (New-Object System.Text.UTF8Encoding($false)))
            Set-Content -LiteralPath $metadataFile -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
            Set-AtomicFixtureStream -Path $metadataFile -Name 'Zone.Identifier.bak' -Bytes ([byte[]]@(0,255,32,13,10,65,97))
            Set-AtomicFixtureStream -Path $metadataFile -Name 'MyZone.Identifier' -Bytes ([byte[]]@(65,97,0,255,13,10,32))
            & compact /c $metadataFile | Out-Null
            $metadataAcl = Get-Acl -LiteralPath $metadataFile
            $metadataSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-21-1111111111-2222222222-3333333333-4444')
            $metadataRule = New-Object System.Security.AccessControl.FileSystemAccessRule($metadataSid, 'ReadData', 'Allow')
            [void]$metadataAcl.AddAccessRule($metadataRule)
            Set-Acl -LiteralPath $metadataFile -AclObject $metadataAcl
            $metadataBefore = Get-FileSnapshot -Path $metadataFile
            $metadataStateBefore = Get-AtomicSuccessState -Path $metadataFile
            $metadataSddlBefore = (Get-Acl -LiteralPath $metadataFile).Sddl
            $metadataOwnerBefore = (Get-Acl -LiteralPath $metadataFile).Owner
            $metadataCompressedBefore = [bool](([int]$metadataBefore.Attributes) -band 0x800)
            $metadataRun = @(Invoke-CleanerWithOptions -Inputs $metadataFile)
            Add-Check -Id 'F2P-37-compression-acl-owner-preserved' -Category 'FAIL_TO_PASS' {
                Assert-True $metadataCompressedBefore 'The fixture file must be compressed before the clean runs.'
                Assert-Equal $metadataRun.Count 1 'A metadata-preservation run must return one result.'
                Assert-Equal $metadataRun[0].Status 'Removed' 'A compressed file carrying an ACL must still be cleaned.'
                $metadataAfter = Get-FileSnapshot -Path $metadataFile
                Assert-True ([bool](([int]$metadataAfter.Attributes) -band 0x800)) 'Cleaning dropped the compression attribute.'
                Assert-Equal $metadataAfter.Hash $metadataBefore.Hash 'Cleaning changed the primary bytes of a compressed file.'
                Assert-Equal $metadataAfter.Length $metadataBefore.Length 'Cleaning changed the primary length of a compressed file.'
                Assert-Equal $metadataAfter.Identity $metadataBefore.Identity 'The file object must not be rebuilt to clean it.'
                Assert-Equal ([string](Get-Acl -LiteralPath $metadataFile).Sddl) $metadataSddlBefore 'Cleaning changed the file ACL.'
                Assert-Equal ([string](Get-Acl -LiteralPath $metadataFile).Owner) $metadataOwnerBefore 'Cleaning changed the file owner.'
                $metadataStateAfter = Get-AtomicSuccessState -Path $metadataFile
                Assert-True (-not $metadataStateAfter.Streams.ContainsKey('Zone.Identifier')) 'Cleaning left the source mark on a compressed file.'
                foreach ($name in @('Zone.Identifier.bak','MyZone.Identifier')) {
                    Assert-True ($metadataStateAfter.Streams.ContainsKey($name)) ('Cleaning removed an unrelated stream: ' + $name)
                    Assert-Equal $metadataStateAfter.Streams[$name] $metadataStateBefore.Streams[$name] ('Cleaning changed unrelated stream bytes: ' + $name)
                }
            }
        }
    }
}
catch {
    $status = 'INVALID'
    $invalidReason = $_.Exception.Message
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$failedChecks = @($checks | Where-Object { -not $_.passed })
if ($status -eq 'RESOLVED' -and $failedChecks.Count -gt 0) {
    $status = 'FAILED'
}

# Binary scoring (Windows 专项 Coding Bench 数据 6.2): no weights, no partial credit.
# Reward 1 only when the run is not INVALID and every required testcase passed; anything
# else is 0. The rubric is reporting metadata only and carries no weight.
$rubricBreakdown = New-Object System.Collections.ArrayList
if ($status -ne 'INVALID') {
    $rubricPath = Join-Path $PSScriptRoot 'rubric.json'
    $rubric = Get-Content -LiteralPath $rubricPath -Raw | ConvertFrom-Json
    foreach ($item in @($rubric.items)) {
        $requiredIds = if ($item.PSObject.Properties.Name -contains 'requires_test_ids') { @($item.requires_test_ids) } else { @() }
        $boundTestIds = @($item.test_ids) + $requiredIds
        $itemPassed = $true
        foreach ($testId in $boundTestIds) {
            $boundCheck = @($checks | Where-Object { $_.test_id -eq $testId })
            if ($boundCheck.Count -ne 1 -or -not $boundCheck[0].passed) {
                $itemPassed = $false
                break
            }
        }
        [void]$rubricBreakdown.Add([pscustomobject][ordered]@{
            rubric_id = [string]$item.rubric_id; passed = $itemPassed; test_ids = @($item.test_ids)
        })
    }
}
$binaryReward = if ($status -ne 'INVALID' -and -not $invalidReason -and $checks.Count -gt 0 -and $failedChecks.Count -eq 0) { 1 } else { 0 }

$finished = Get-Date
$resultDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $resultDirectory | Out-Null
$osInfo = $null
try { $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop } catch {}
$systemState = [ordered]@{
    captured_at = $finished.ToUniversalTime().ToString('o')
    os_caption = if ($null -ne $osInfo) { [string]$osInfo.Caption } else { [System.Environment]::OSVersion.VersionString }
    os_version = if ($null -ne $osInfo) { [string]$osInfo.Version } else { [System.Environment]::OSVersion.Version.ToString() }
    os_build = if ($null -ne $osInfo) { [string]$osInfo.BuildNumber } else { [System.Environment]::OSVersion.Version.Build }
    architecture = [System.Environment]::GetEnvironmentVariable('PROCESSOR_ARCHITECTURE')
    powershell_version = $PSVersionTable.PSVersion.ToString()
    powershell_edition = [string]$PSVersionTable.PSEdition
    workspace_root = $WorkspaceRoot
}
$result = [ordered]@{
    task_id = 'windows-powershell-ads-001'
        task_version = '1.3.0'
    rewardkit_version = 'rewardkit-0.1.0-pilot'
    run_id = [guid]::NewGuid().ToString('N')
    status = $status
    resolved = ($status -eq 'RESOLVED')
    reward = $binaryReward
    programmatic_score = $binaryReward
    score_method = 'binary_all_required'
    partial_credit = $false
    rubric_breakdown = @($rubricBreakdown)
    tests_total = $checks.Count
    tests_passed = @($checks | Where-Object { $_.passed }).Count
    tests_failed = $failedChecks.Count
    tests_skipped = 0
    FAIL_TO_PASS = @($checks | Where-Object { $_.category -eq 'FAIL_TO_PASS' })
    PASS_TO_PASS = @($checks | Where-Object { $_.category -eq 'PASS_TO_PASS' })
    invalid_reason = $invalidReason
    started_at = $started.ToUniversalTime().ToString('o')
    finished_at = $finished.ToUniversalTime().ToString('o')
    duration_seconds = [math]::Round(($finished - $started).TotalSeconds, 3)
    environment_digest = ('host:{0};build:{1};pwsh:{2}' -f $systemState.os_caption, $systemState.os_build, $systemState.powershell_version)
        evaluator_version = 'windows-powershell-ads-evaluator-1.3.0'
    artifact_hash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $WorkspaceRoot 'src\ZoneMarkCleaner.ps1')).Hash
    checks = $checks
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
$systemState | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $resultDirectory 'system_state.json') -Encoding UTF8

$testCases = foreach ($check in @($checks)) {
    $name = [System.Security.SecurityElement]::Escape([string]$check.test_id)
    $className = [System.Security.SecurityElement]::Escape([string]$check.category)
    if ($check.passed) {
        ('  <testcase classname="{0}" name="{1}" />' -f $className, $name)
    }
    else {
        $message = [System.Security.SecurityElement]::Escape([string]$check.failure_reason)
        ('  <testcase classname="{0}" name="{1}"><failure message="{2}" /></testcase>' -f $className, $name, $message)
    }
}
$junit = @(
    '<?xml version="1.0" encoding="utf-8"?>'
    ('<testsuite name="windows-powershell-ads-001" tests="{0}" failures="{1}" errors="{2}" time="{3}">' -f $checks.Count, $failedChecks.Count, $(if ($status -eq 'INVALID') { 1 } else { 0 }), $result.duration_seconds)
    $testCases
    '</testsuite>'
) -join [Environment]::NewLine
[System.IO.File]::WriteAllText((Join-Path $resultDirectory 'junit.xml'), $junit, (New-Object System.Text.UTF8Encoding($false)))

$logLines = @(
    "task_id=windows-powershell-ads-001"
        "task_version=1.3.0"
    "status=$status"
    "started_at=$($result.started_at)"
    "finished_at=$($result.finished_at)"
    "duration_seconds=$($result.duration_seconds)"
    "tests_total=$($result.tests_total)"
    "tests_passed=$($result.tests_passed)"
    "tests_failed=$($result.tests_failed)"
) + @($checks | ForEach-Object { "[$(if ($_.passed) {'PASS'} else {'FAIL'})] $($_.test_id) $($_.failure_reason)" })
$logLines | Set-Content -LiteralPath (Join-Path $resultDirectory 'test.log') -Encoding UTF8

if ($status -eq 'INVALID') {
    exit 2
}
exit 0
