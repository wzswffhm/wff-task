param([string]$ResultsDir)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'tool_invoke.ps1')
. (Join-Path $PSScriptRoot 'acl_shape_matrix.ps1')
. (Join-Path $PSScriptRoot 'acl_equivalence.ps1')
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class WorkflowProbe {
    [StructLayout(LayoutKind.Sequential, Pack=4)]
    public struct Info {
        public uint Attributes;
        public long Created, Accessed, Written;
        public uint Volume, SizeHigh, SizeLow, Links, High, Low;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern SafeFileHandle CreateFileW(string path, uint access, uint share, IntPtr security, uint mode, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool GetFileInformationByHandle(SafeFileHandle handle, out Info info);
    public static string Identity(string path) {
        using(var handle=CreateFileW(path,0,7,IntPtr.Zero,3,0x02200000,IntPtr.Zero)) {
            Info info;
            if(handle.IsInvalid || !GetFileInformationByHandle(handle,out info)) throw new System.ComponentModel.Win32Exception();
            return info.Volume.ToString("X8")+":"+info.High.ToString("X8")+info.Low.ToString("X8");
        }
    }
    public static bool CanWriteAcl(string path) {
        using(var handle=CreateFileW(path,0x60000,7,IntPtr.Zero,3,0x02200000,IntPtr.Zero)) return !handle.IsInvalid;
    }
}
'@
$workspace = Get-TaskWorkspace
$fixture = Join-Path (Get-PathAclFixtureRoot) 'workflow'
New-Item -ItemType Directory -Path $fixture | Out-Null
$observations = [ordered]@{}
$verdicts = @{}
$usersSid = [Security.Principal.SecurityIdentifier]::new('S-1-5-32-545')
$currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User

function New-WorkflowTree([string]$Name) {
    $caseRoot = Join-Path $fixture $Name
    $root = Join-Path $caseRoot 'stage-审批'
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $security = [Security.AccessControl.DirectorySecurity]::new()
    $security.SetOwner($currentSid)
    $security.SetAccessRuleProtection($true,$false)
    $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($currentSid,'FullControl','ContainerInherit, ObjectInherit','None','Allow'))
    $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($usersSid,'Modify','None','None','Allow'))
    Set-Acl -LiteralPath $root -AclObject $security
    $directory = Join-Path $root 'ordinary'
    New-Item -ItemType Directory -Path $directory | Out-Null
    $leaf = Join-Path $directory 'payload.txt'
    $late = Join-Path $directory 'zz-late.txt'
    [IO.File]::WriteAllText($leaf,'payload')
    [IO.File]::WriteAllText($late,'late')
    $security = Get-Acl -LiteralPath $leaf
    $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($usersSid,'Modify','Allow'))
    Set-Acl -LiteralPath $leaf -AclObject $security
    return @{home=$caseRoot;root=$root;directory=$directory;leaf=$leaf;late=$late;plan=(Join-Path $caseRoot 'approval.json')}
}
function Invoke-Workflow([string[]]$Command) {
    Invoke-PathAclTool -Workspace $workspace -ExtraArguments $Command
}
function Save-Plan($Tree) { Invoke-Workflow @('--plan',$Tree.root,$Tree.plan) }
function Apply-Plan($Tree) { Invoke-Workflow @('--apply',$Tree.plan) }
function Get-State([string[]]$Paths) {
    $state = [ordered]@{}
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) { $state[$path] = 'MISSING'; continue }
        $item = Get-Item -LiteralPath $path -Force
        $state[$path] = @{
            identity=[WorkflowProbe]::Identity($path)
            security=(Get-DescriptorSignature $path)
            attributes=[int]$item.Attributes
            data=$(if (-not $item.PSIsContainer -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { [Convert]::ToBase64String([IO.File]::ReadAllBytes($path)) } else { '' })
        }
    }
    return ($state | ConvertTo-Json -Depth 8 -Compress)
}
function Tree-Paths($Tree) { return @($Tree.root,$Tree.directory,$Tree.leaf,$Tree.late) }
function Test-Reconciled($Tree) {
    foreach ($path in @($Tree.directory,$Tree.leaf,$Tree.late)) {
        $inherited = @((Get-Acl -LiteralPath $path).Access | Where-Object {
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq 'S-1-5-32-545' -and
            $_.AccessControlType -eq 'Allow' -and $_.IsInherited -and
            (($_.FileSystemRights.value__ -band (-bnot 0x100000)) -eq 0x301bf)
        })
        if ($inherited.Count -eq 0) { return $false }
    }
    return $true
}
function Read-CandidatePlan($Tree) {
    if (-not (Test-Path -LiteralPath $Tree.plan -PathType Leaf)) { return $null }
    try { $text = [IO.File]::ReadAllText($Tree.plan) }
    catch [IO.FileNotFoundException] { return $null }
    catch [IO.DirectoryNotFoundException] { return $null }
    catch [UnauthorizedAccessException] { return $null }
    try { $document = $text | ConvertFrom-Json }
    catch { return $null } # Candidate JSON is data, not a fixture setup operation.
    if ($null -eq $document -or -not ($document.PSObject.Properties.Name -contains 'formatVersion') -or
        -not ($document.PSObject.Properties.Name -contains 'entries') -or @($document.entries).Count -eq 0 -or
        $null -eq @($document.entries)[0] -or
        -not (@($document.entries)[0].PSObject.Properties.Name -contains 'relativePath')) { return $null }
    return $document
}
function Test-OperatorDocument([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try { return [IO.File]::ReadAllText($Path) -ceq 'operator-document' }
    catch [IO.FileNotFoundException] { return $false }
    catch [IO.DirectoryNotFoundException] { return $false }
    catch [UnauthorizedAccessException] { return $false }
}
function Record([int]$Number,[bool]$Passed,$Detail) {
    $identifier = 'F2P-{0:000}' -f $Number
    $verdicts[$identifier] = $Passed
    $observations[$identifier] = $Detail
}
function Assert-Conflict($Tree,[string[]]$Paths,[int]$Expected=3) {
    $before = Get-State $Paths
    $applied = Apply-Plan $Tree
    $after = Get-State $Paths
    $prefix = switch ($Expected) { 3 {'acl-conflict'} 4 {'acl-unsafe'} }
    $reportMatches = if ($Expected -eq 2) { $true } else { $applied.output.Contains($prefix) }
    return @{passed=($applied.code -eq $Expected -and $reportMatches -and $before -ceq $after);before=$before;after=$after;receipt=$applied}
}

$tree = New-WorkflowTree 'readonly'
$before = Get-State (Tree-Paths $tree)
$planned = Save-Plan $tree
$after = Get-State (Tree-Paths $tree)
$validEnvelope = $false
if (Test-Path -LiteralPath $tree.plan) {
    try {
        $envelope = Get-Content -LiteralPath $tree.plan -Raw -Encoding UTF8 | ConvertFrom-Json
        $validEnvelope = $envelope.formatVersion -eq 1 -and $envelope.rootPath -eq $tree.root -and @($envelope.entries).Count -eq 4
    } catch { $validEnvelope = $false }
}
Record 9 ($planned.code -eq 0 -and $validEnvelope -and $before -ceq $after) @{before=$before;after=$after;plan=$planned}

$tree = New-WorkflowTree 'portable'
$planned = Save-Plan $tree
$portable = Join-Path $tree.home 'renamed-副本.json'
if (Test-Path -LiteralPath $tree.plan) { Copy-Item -LiteralPath $tree.plan -Destination $portable; Remove-Item -LiteralPath $tree.plan }
$tree.plan = $portable
$applied = Apply-Plan $tree
Record 10 ($planned.code -eq 0 -and $applied.code -eq 0 -and (Test-Reconciled $tree)) @{plan=$planned;apply=$applied;state=(Get-State (Tree-Paths $tree))}

$tree = New-WorkflowTree 'root-replaced'
$planned = Save-Plan $tree
$original = [WorkflowProbe]::Identity($tree.root)
$rootSecurity = Get-Acl -LiteralPath $tree.root
$rootStamp = [IO.Directory]::GetLastWriteTimeUtc($tree.root)
$moved = Join-Path $tree.home 'retired'
[IO.Directory]::Move($tree.root,$moved)
New-Item -ItemType Directory -Path $tree.root | Out-Null
Set-Acl -LiteralPath $tree.root -AclObject $rootSecurity
[IO.Directory]::Move((Join-Path $moved 'ordinary'),$tree.directory)
[IO.Directory]::SetLastWriteTimeUtc($tree.root,$rootStamp)
$check = Assert-Conflict $tree @($tree.root,$moved)
Record 11 ($planned.code -eq 0 -and $check.passed -and [WorkflowProbe]::Identity($tree.root) -ne $original) $check

$tree = New-WorkflowTree 'leaf-replaced'
$planned = Save-Plan $tree
$original = [WorkflowProbe]::Identity($tree.leaf)
$security = Get-Acl -LiteralPath $tree.leaf
$stamp = [IO.File]::GetLastWriteTimeUtc($tree.leaf)
$created = [IO.File]::GetCreationTimeUtc($tree.leaf)
$retired = Join-Path $tree.home 'retired-file'
[IO.File]::Move($tree.leaf,$retired)
[IO.File]::Copy($retired,$tree.leaf)
Set-Acl -LiteralPath $tree.leaf -AclObject $security
[IO.File]::SetLastWriteTimeUtc($tree.leaf,$stamp)
[IO.File]::SetCreationTimeUtc($tree.leaf,$created)
$check = Assert-Conflict $tree ((Tree-Paths $tree) + @($retired))
Record 12 ($planned.code -eq 0 -and $check.passed -and [WorkflowProbe]::Identity($tree.leaf) -ne $original) $check

$details = @()
foreach ($drift in @('dacl','owner','group','protection')) {
    $tree = New-WorkflowTree ('late-security-'+$drift)
    $planned = Save-Plan $tree
    $security = Get-Acl -LiteralPath $tree.late
    $originalSecurity = $security.Sddl
    switch ($drift) {
        'dacl' { $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-32-546'),'Read','Allow')) }
        'owner' {
            $owner = $security.GetOwner([Security.Principal.SecurityIdentifier])
            $replacement = if ($owner.Value -eq $currentSid.Value) { [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544') } else { $currentSid }
            $security.SetOwner($replacement)
        }
        'group' {
            $group = $security.GetGroup([Security.Principal.SecurityIdentifier])
            $replacement = if ($group.Value -eq $currentSid.Value) { [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544') } else { $currentSid }
            $security.SetGroup($replacement)
        }
        'protection' { $security.SetAccessRuleProtection($true,$true) }
    }
    Set-Acl -LiteralPath $tree.late -AclObject $security
    if ((Get-Acl -LiteralPath $tree.late).Sddl -ceq $originalSecurity) { throw "Security drift fixture did not persist: $drift" }
    $check = Assert-Conflict $tree (Tree-Paths $tree)
    $details += @{drift=$drift;passed=($planned.code -eq 0 -and $check.passed);check=$check}
}
Record 13 (@($details | Where-Object { -not $_.passed }).Count -eq 0) $details

$tree = New-WorkflowTree 'added'
$planned = Save-Plan $tree
$added = Join-Path $tree.directory 'new-arrival.txt'
[IO.File]::WriteAllText($added,'new')
$check = Assert-Conflict $tree ((Tree-Paths $tree) + @($added))
Record 14 ($planned.code -eq 0 -and $check.passed) $check

$details = @()
foreach ($operation in @('removed','renamed')) {
    $tree = New-WorkflowTree $operation
    $planned = Save-Plan $tree
    $renamed = Join-Path $tree.directory 'renamed.txt'
    if ($operation -eq 'removed') { [IO.File]::Delete($tree.late) } else { [IO.File]::Move($tree.late,$renamed) }
    $check = Assert-Conflict $tree ((Tree-Paths $tree) + @($renamed))
    $details += @{passed=($planned.code -eq 0 -and $check.passed);check=$check}
}
Record 15 (@($details | Where-Object { -not $_.passed }).Count -eq 0) $details

$tree = New-WorkflowTree 'boundary-swap'
$target = Join-Path $tree.home 'external'
New-Item -ItemType Directory -Path $target | Out-Null
$junction = Join-Path $tree.root 'boundary'
New-Item -ItemType Junction -Path $junction -Target $target | Out-Null
$planned = Save-Plan $tree
$oldIdentity = [WorkflowProbe]::Identity($junction)
$retired = Join-Path $tree.home 'old-boundary'
[IO.Directory]::Move($junction,$retired)
New-Item -ItemType Junction -Path $junction -Target $target | Out-Null
$check = Assert-Conflict $tree ((Tree-Paths $tree) + @($target))
Record 16 ($planned.code -eq 0 -and $check.passed -and $oldIdentity -ne [WorkflowProbe]::Identity($junction)) $check

$tree = New-WorkflowTree 'excluded-changes'
$private = Join-Path $tree.root 'private'
$target = Join-Path $tree.home 'external'
New-Item -ItemType Directory -Path $private,$target | Out-Null
$security = Get-Acl -LiteralPath $private
$security.SetAccessRuleProtection($true,$true)
Set-Acl -LiteralPath $private -AclObject $security
$junction = Join-Path $tree.root 'boundary'
New-Item -ItemType Junction -Path $junction -Target $target | Out-Null
$planned = Save-Plan $tree
$privateFile = Join-Path $private 'added-after-plan.txt'
$externalFile = Join-Path $target 'outside.txt'
[IO.File]::WriteAllText($privateFile,'private')
[IO.File]::WriteAllText($externalFile,'external')
$excludedBefore = Get-State @($private,$privateFile,$target,$externalFile)
$applied = Apply-Plan $tree
$excludedAfter = Get-State @($private,$privateFile,$target,$externalFile)
Record 17 ($planned.code -eq 0 -and $applied.code -eq 0 -and (Test-Reconciled $tree) -and $excludedBefore -ceq $excludedAfter -and $applied.output -match 'protected=1(?=[:\s]|$)' -and $applied.output -match 'reparse=1(?=[:\s]|$)') @{plan=$planned;apply=$applied;before=$excludedBefore;after=$excludedAfter}

$tree = New-WorkflowTree 'data-churn'
$planned = Save-Plan $tree
[IO.File]::WriteAllText($tree.leaf,'changed-length-and-content')
Set-Content -LiteralPath $tree.leaf -Stream deployment -Value 'ads-latest' -NoNewline -Encoding ASCII
[IO.File]::SetAttributes($tree.leaf,[IO.FileAttributes]::Hidden)
$applied = Apply-Plan $tree
$newFile = Join-Path $tree.directory 'future.txt'
[IO.File]::WriteAllText($newFile,'new')
Record 18 ($planned.code -eq 0 -and $applied.code -eq 0 -and (Test-Reconciled $tree) -and [IO.File]::ReadAllText($tree.leaf) -ceq 'changed-length-and-content' -and (Get-Content -LiteralPath $tree.leaf -Stream deployment -Raw) -ceq 'ads-latest' -and ([IO.File]::GetAttributes($tree.leaf) -band [IO.FileAttributes]::Hidden) -ne 0) @{plan=$planned;apply=$applied;state=(Get-State (Tree-Paths $tree))}

$tree = New-WorkflowTree 'external-hardlink'
$alias = Join-Path $tree.home 'outside-alias.txt'
New-Item -ItemType HardLink -Path $alias -Target $tree.late | Out-Null
if ([WorkflowProbe]::Identity($alias) -ne [WorkflowProbe]::Identity($tree.late)) { throw 'Hardlink fixture did not alias the same NTFS identity.' }
$before = Get-State ((Tree-Paths $tree) + @($alias))
$planned = Save-Plan $tree
$direct = Invoke-Workflow @($tree.root)
$after = Get-State ((Tree-Paths $tree) + @($alias))
Record 19 ($planned.code -eq 4 -and $direct.code -eq 4 -and $before -ceq $after) @{plan=$planned;direct=$direct;before=$before;after=$after}

$tree = New-WorkflowTree 'hardlink-after-plan'
$planned = Save-Plan $tree
$alias = Join-Path $tree.home 'outside-alias.txt'
New-Item -ItemType HardLink -Path $alias -Target $tree.late | Out-Null
$check = Assert-Conflict $tree ((Tree-Paths $tree) + @($alias)) 4
Record 20 ($planned.code -eq 0 -and $check.passed) $check

$tree = New-WorkflowTree 'internal-hardlink'
$alias = Join-Path $tree.directory 'inside-alias.txt'
New-Item -ItemType HardLink -Path $alias -Target $tree.leaf | Out-Null
$before = Get-State ((Tree-Paths $tree) + @($alias))
$planned = Save-Plan $tree
$direct = Invoke-Workflow @($tree.root)
$after = Get-State ((Tree-Paths $tree) + @($alias))
Record 21 ($planned.code -eq 4 -and $direct.code -eq 4 -and $before -ceq $after) @{plan=$planned;direct=$direct;before=$before;after=$after}

$tree = New-WorkflowTree 'access-preflight'
$security = Get-Acl -LiteralPath $tree.late
$security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'ChangePermissions','Deny'))
$security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-3-4'),'ReadPermissions','Allow'))
Set-Acl -LiteralPath $tree.late -AclObject $security
if ([WorkflowProbe]::CanWriteAcl($tree.late)) { throw 'WRITE_DAC denial fixture is ineffective under this token.' }
$before = Get-State (Tree-Paths $tree)
$planned = Save-Plan $tree
$applied = Apply-Plan $tree
$direct = Invoke-Workflow @($tree.root)
$after = Get-State (Tree-Paths $tree)
$renamedRoot = Join-Path $tree.home 'released-handles'
[IO.Directory]::Move($tree.root,$renamedRoot)
[IO.Directory]::Move($renamedRoot,$tree.root)
Record 22 ($planned.code -eq 0 -and $applied.code -eq 1 -and $direct.code -eq 1 -and $before -ceq $after) @{plan=$planned;apply=$applied;direct=$direct;before=$before;after=$after;write_dac_denied=$true;handles_released=$true}

$details = @()
foreach ($mutation in @('version','escape','duplicate','missing-root','malformed')) {
    $tree = New-WorkflowTree ('invalid-'+$mutation)
    $planned = Save-Plan $tree
    $document = Read-CandidatePlan $tree
    $mutationReady = $null -ne $document
    if ($mutationReady) {
        switch ($mutation) {
            'version' { $document.formatVersion = 99 }
            'escape' { $document.entries[0].relativePath = '..\outside' }
            'duplicate' { $document.entries = @($document.entries) + @($document.entries[0]) }
            'missing-root' { $document.entries = @($document.entries | Where-Object { $_.relativePath -ne '.' }) }
        }
        if ($mutation -eq 'malformed') { [IO.File]::WriteAllText($tree.plan,'{broken') }
        else { $document | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $tree.plan -Encoding UTF8 }
    }
    $check = Assert-Conflict $tree (Tree-Paths $tree) 2
    $details += @{mutation=$mutation;passed=($planned.code -eq 0 -and $mutationReady -and $check.passed);candidate_plan_readable=$mutationReady;check=$check}
}
Record 23 (@($details | Where-Object { -not $_.passed }).Count -eq 0) $details

$tree = New-WorkflowTree 'replay'
$planned = Save-Plan $tree
$first = Apply-Plan $tree
$stale = Assert-Conflict $tree (Tree-Paths $tree)
$tree.plan = Join-Path $tree.home 'fresh.json'
$fresh = Save-Plan $tree
$before = Get-State (Tree-Paths $tree)
$second = Apply-Plan $tree
$after = Get-State (Tree-Paths $tree)
Record 24 ($planned.code -eq 0 -and $first.code -eq 0 -and $stale.passed -and $fresh.code -eq 0 -and $second.code -eq 0 -and (Test-Reconciled $tree) -and $before -ceq $after) @{first=$first;stale=$stale;fresh=$fresh;second=$second;before=$before;after=$after}

$tree = New-WorkflowTree 'plan-output-safety'
$before = Get-State (Tree-Paths $tree)
[IO.File]::WriteAllText($tree.plan,'operator-document')
$overwrite = Save-Plan $tree
$inside = Invoke-Workflow @('--plan',$tree.root,(Join-Path $tree.root 'approval.json'))
$missing = Join-Path $tree.home 'absent'
$missingResult = Invoke-Workflow @('--plan',$missing,(Join-Path $tree.home 'missing.json'))
$after = Get-State (Tree-Paths $tree)
Record 25 ($overwrite.code -ne 0 -and (Test-OperatorDocument $tree.plan) -and $inside.code -ne 0 -and -not (Test-Path -LiteralPath (Join-Path $tree.root 'approval.json')) -and $missingResult.code -ne 0 -and -not (Test-Path -LiteralPath $missing) -and $before -ceq $after) @{overwrite=$overwrite;inside=$inside;missing=$missingResult;before=$before;after=$after}

$tree = New-WorkflowTree 'protected-alias'
$protected = Join-Path $tree.root 'private.txt'
[IO.File]::WriteAllText($protected,'private')
$security = Get-Acl -LiteralPath $protected
$security.SetAccessRuleProtection($true,$true)
Set-Acl -LiteralPath $protected -AclObject $security
$alias = Join-Path $tree.home 'external-private.txt'
New-Item -ItemType HardLink -Path $alias -Target $protected | Out-Null
$before = Get-State @($protected,$alias)
$planned = Save-Plan $tree
$applied = Apply-Plan $tree
$after = Get-State @($protected,$alias)
Record 26 ($planned.code -eq 0 -and $applied.code -eq 0 -and (Test-Reconciled $tree) -and $before -ceq $after -and $applied.output -match 'protected=1(?=[:\s]|$)') @{plan=$planned;apply=$applied;before=$before;after=$after}

$observations | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $ResultsDir 'artifacts\workflow-observations.json') -Encoding UTF8
return ,$verdicts
