#Requires -Version 5.1
param([string]$ResultsDir = "results")
$ErrorActionPreference = "Stop"
$ConfirmPreference = "None"
$ProgressPreference = "SilentlyContinue"
$PSDefaultParameterValues["*:Confirm"] = $false
. (Join-Path $PSScriptRoot "tool_invoke.ps1")
. (Join-Path $PSScriptRoot 'acl_shape_matrix.ps1')
. (Join-Path $PSScriptRoot 'acl_equivalence.ps1')

function Get-UsersRules([string]$Path) {
  $sid = "S-1-5-32-545"
  @(Get-Acl -LiteralPath $Path | ForEach-Object { $_.Access } | Where-Object {
    $identity = $null
    try { $identity = $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { $identity = $null }
    $identity -eq $sid -and $_.AccessControlType -eq "Allow" -and
      (($_.FileSystemRights.value__ -band (-bnot [int][Security.AccessControl.FileSystemRights]::Synchronize)) -eq [int][Security.AccessControl.FileSystemRights]::Modify)
  })
}
function Get-UsersAllowRules([string]$Path) {
  $sid = "S-1-5-32-545"
  @(Get-Acl -LiteralPath $Path | ForEach-Object { $_.Access } | Where-Object {
    $identity = $null
    try { $identity = $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { $identity = $null }
    $identity -eq $sid -and $_.AccessControlType -eq "Allow"
  })
}
function Test-InheritedUsersModify([string]$Path) { @(Get-UsersRules $Path | Where-Object { $_.IsInherited }).Count -gt 0 }
function Test-NoExplicitUsersModify([string]$Path) { @(Get-UsersRules $Path | Where-Object { -not $_.IsInherited }).Count -eq 0 }
function Test-IdentityPresent([string]$Path, [string]$Sid, [string]$ControlType) {
  @((Get-Acl -LiteralPath $Path).Access | Where-Object {
    $identity = $null
    try { $identity = $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { $identity = $null }
    $identity -eq $Sid -and $_.AccessControlType.ToString() -eq $ControlType
  }).Count -gt 0
}

try {
$workspace = Get-TaskWorkspace
$fixtureRoot = Get-PathAclFixtureRoot
if (Test-Path -LiteralPath $fixtureRoot) { throw 'Fixture root must be fresh.' }
New-Item -ItemType Directory -Force -Path $fixtureRoot | Out-Null
$outsideTarget = Join-Path $fixtureRoot "junction-target-保持不变"
$outsideFile = Join-Path $fixtureRoot "symlink-target-保持不变.txt"
if (-not (Invoke-PathAclBuild -Workspace $workspace)) {
  New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
  '{"failure_class":"candidate_build"}' | Set-Content (Join-Path $ResultsDir 'candidate-build-failure.json')
  return (New-FailedF2P)
}

$staging = Join-Path $fixtureRoot "数据暂存-深度"
if (Test-Path -LiteralPath $staging) { throw 'Staging fixture must be fresh.' }
New-Item -ItemType Directory -Force -Path $staging | Out-Null
$seedAcl = Get-Acl -LiteralPath $staging
$seedAcl.SetAccessRuleProtection($true, $false)
$authenticatedUsers = [Security.Principal.SecurityIdentifier]::new("S-1-5-11")
$seedAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
  $authenticatedUsers, "Modify", "ContainerInherit, ObjectInherit", "None", "Allow"))
Set-Acl -LiteralPath $staging -AclObject $seedAcl

$existing = Join-Path $staging "迁移前\普通工作区"
$existingFile = Join-Path $existing "已存在.txt"
$staleFile = Join-Path $existing "旧显式授权.txt"
$writeOnlyFile = Join-Path $existing "仅写入.txt"
$broadFile = Join-Path $existing "保留完整权限.txt"
$attrFile = Join-Path $existing "属性标记.txt"
$private = Join-Path $staging "迁移前\私有区域"
$secret = Join-Path $private "保密.txt"
$protectedFile = Join-Path $staging "迁移前\受保护文件.txt"
$junction = Join-Path $staging "迁移前\外部联接"
$symlink = Join-Path $staging "迁移前\外部符号.txt"
New-Item -ItemType Directory -Force -Path $existing, $private, $outsideTarget | Out-Null
"before" | Set-Content -LiteralPath $existingFile -Encoding UTF8
"stale" | Set-Content -LiteralPath $staleFile -Encoding UTF8
"write-only" | Set-Content -LiteralPath $writeOnlyFile -Encoding UTF8
"broad-rights" | Set-Content -LiteralPath $broadFile -Encoding UTF8
"attr" | Set-Content -LiteralPath $attrFile -Encoding UTF8
"private" | Set-Content -LiteralPath $secret -Encoding UTF8
"protected-file" | Set-Content -LiteralPath $protectedFile -Encoding UTF8
"outside-target" | Set-Content -LiteralPath (Join-Path $outsideTarget "目标内容.txt") -Encoding UTF8
"outside-file" | Set-Content -LiteralPath $outsideFile -Encoding UTF8
Set-Content -Path ($existingFile + ":Zone.Identifier") -Value "[ZoneTransfer]`r`nZoneId=3" -Encoding ASCII
$adsBefore = Get-Content -Path ($existingFile + ":Zone.Identifier") -Raw -ErrorAction SilentlyContinue

$privateAcl = Get-Acl -LiteralPath $private
$privateAcl.SetAccessRuleProtection($true, $true)
Set-Acl -LiteralPath $private -AclObject $privateAcl
$protectedBefore = (Get-Acl -LiteralPath $private).Sddl
$secretBefore = (Get-Acl -LiteralPath $secret).Sddl
$secretContentBefore = Get-Content -LiteralPath $secret -Raw
$protectedFileAcl = Get-Acl -LiteralPath $protectedFile
$protectedFileAcl.SetAccessRuleProtection($true, $true)
Set-Acl -LiteralPath $protectedFile -AclObject $protectedFileAcl
$protectedFileBefore = (Get-Acl -LiteralPath $protectedFile).Sddl
$protectedFileContentBefore = Get-Content -LiteralPath $protectedFile -Raw

if (Test-Path -LiteralPath $junction) { Remove-Item -LiteralPath $junction -Force }
New-Item -ItemType Junction -Path $junction -Target $outsideTarget -Force | Out-Null
if (Test-Path -LiteralPath $symlink) { Remove-Item -LiteralPath $symlink -Force }
New-Item -ItemType SymbolicLink -Path $symlink -Target $outsideFile -Force | Out-Null
$outsideTargetBefore = (Get-Acl -LiteralPath $outsideTarget).Sddl
$outsideContentBefore = Get-Content -LiteralPath (Join-Path $outsideTarget "目标内容.txt") -Raw
$outsideFileBefore = Get-Content -LiteralPath $outsideFile -Raw
$outsideFileAclBefore = (Get-Acl -LiteralPath $outsideFile).Sddl

$rootAcl = Get-Acl -LiteralPath $staging
$users = [Security.Principal.SecurityIdentifier]::new("S-1-5-32-545")
$admins = [Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
$guests = [Security.Principal.SecurityIdentifier]::new("S-1-5-32-546")
$rootAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($users, "Modify", "None", "None", "Allow"))
$rootAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($admins, "ReadAndExecute", "None", "None", "Allow"))
Set-Acl -LiteralPath $staging -AclObject $rootAcl

$staleAcl = Get-Acl -LiteralPath $staleFile
$staleAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($users, "Modify", "None", "None", "Allow"))
$staleAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($admins, "ReadAndExecute", "None", "None", "Allow"))
$staleAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($guests, "FullControl", "None", "None", "Deny"))
Set-Acl -LiteralPath $staleFile -AclObject $staleAcl
$ownerBefore = (Get-Acl -LiteralPath $staleFile).Owner

$writeAcl = Get-Acl -LiteralPath $writeOnlyFile
$writeAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($users, "Write", "None", "None", "Allow"))
Set-Acl -LiteralPath $writeOnlyFile -AclObject $writeAcl

$broadAcl = Get-Acl -LiteralPath $broadFile
$broadAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($users, "FullControl", "None", "None", "Allow"))
Set-Acl -LiteralPath $broadFile -AclObject $broadAcl
$broadBefore = @((Get-Acl -LiteralPath $broadFile).Access | Where-Object { -not $_.IsInherited } | ForEach-Object { $_.IdentityReference.Value + ':' + $_.FileSystemRights.value__ + ':' + $_.AccessControlType }) -join '|'
$denyBefore = @((Get-Acl -LiteralPath $staleFile).Access | Where-Object { $_.AccessControlType -eq 'Deny' } | ForEach-Object { $_.IdentityReference.Value + ':' + $_.FileSystemRights.value__ + ':' + $_.InheritanceFlags + ':' + $_.PropagationFlags }) -join '|'

$creatorOwner = [Security.Principal.SecurityIdentifier]::new("S-1-3-0")
$existingAcl = Get-Acl -LiteralPath $existing
$existingAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
  $creatorOwner, "FullControl", "ContainerInherit, ObjectInherit", "InheritOnly", "Allow"))
Set-Acl -LiteralPath $existing -AclObject $existingAcl
$attrItem = Get-Item -LiteralPath $attrFile -Force
$attrItem.Attributes = $attrItem.Attributes -bor [IO.FileAttributes]::Hidden -bor [IO.FileAttributes]::System

$first = Invoke-PathAclTool -Workspace $workspace -Argument $staging
if ($first.code -ne 0) { return (New-FailedF2P) }
$out = [string]$first.output

$rootRules = @(Get-UsersRules $staging | Where-Object {
  -not $_.IsInherited -and $_.InheritanceFlags.ToString() -match "ContainerInherit" -and
  $_.InheritanceFlags.ToString() -match "ObjectInherit" -and $_.PropagationFlags.ToString() -eq "None"
})
$newDir = Join-Path $staging "运行后\嵌套"
$newFile = Join-Path $newDir "新文件.txt"
New-Item -ItemType Directory -Force -Path $newDir | Out-Null
"after" | Set-Content -LiteralPath $newFile -Encoding UTF8

$staleAdminsRemain = Test-IdentityPresent $staleFile "S-1-5-32-544" "Allow"
$denyGuestsRemain = Test-IdentityPresent $staleFile "S-1-5-32-546" "Deny"
$writeOnlyExplicit = @(Get-UsersAllowRules $writeOnlyFile | Where-Object {
  -not $_.IsInherited -and
    (($_.FileSystemRights.value__ -band [int][Security.AccessControl.FileSystemRights]::Write) -ne 0) -and
    (($_.FileSystemRights.value__ -band [int][Security.AccessControl.FileSystemRights]::Modify) -ne [int][Security.AccessControl.FileSystemRights]::Modify)
}).Count -gt 0
$adsAfter = Get-Content -Path ($existingFile + ":Zone.Identifier") -Raw -ErrorAction SilentlyContinue
$ownerAfter = (Get-Acl -LiteralPath $staleFile).Owner
$creatorOwnerRemains = @((Get-Acl -LiteralPath $existing).Access | Where-Object {
  $identity = $null
  try { $identity = $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { $identity = $null }
  $identity -eq "S-1-3-0" -and -not $_.IsInherited -and $_.PropagationFlags.ToString() -match "InheritOnly"
}).Count -gt 0
$attrAfter = (Get-Item -LiteralPath $attrFile -Force).Attributes
$attrsRemain = (($attrAfter -band [IO.FileAttributes]::Hidden) -ne 0) -and (($attrAfter -band [IO.FileAttributes]::System) -ne 0)

$broadAfter = @((Get-Acl -LiteralPath $broadFile).Access | Where-Object { -not $_.IsInherited } | ForEach-Object { $_.IdentityReference.Value + ':' + $_.FileSystemRights.value__ + ':' + $_.AccessControlType }) -join '|'
$denyAfter = @((Get-Acl -LiteralPath $staleFile).Access | Where-Object { $_.AccessControlType -eq 'Deny' } | ForEach-Object { $_.IdentityReference.Value + ':' + $_.FileSystemRights.value__ + ':' + $_.InheritanceFlags + ':' + $_.PropagationFlags }) -join '|'
$f2p001 = ($rootRules.Count -eq 1 -and @(Get-UsersRules $staging | Where-Object { -not $_.IsInherited }).Count -eq 1)
$f2p002 = ((Test-InheritedUsersModify $existing) -and (Test-InheritedUsersModify $existingFile) -and (Test-InheritedUsersModify $staleFile) -and (Test-NoExplicitUsersModify $staleFile) -and $staleAdminsRemain -and $writeOnlyExplicit -and (Test-InheritedUsersModify $writeOnlyFile) -and $broadBefore -eq $broadAfter -and (Test-InheritedUsersModify $broadFile))
$f2p003 = ((Test-InheritedUsersModify $newDir) -and (Test-InheritedUsersModify $newFile))
$privSddlOk = ((Get-Acl -LiteralPath $private).Sddl -eq $protectedBefore)
$protFileSddlOk = ((Get-Acl -LiteralPath $protectedFile).Sddl -eq $protectedFileBefore)
$protFileBodyOk = ((Get-Content -LiteralPath $protectedFile -Raw) -eq $protectedFileContentBefore)
$secretSddlOk = ((Get-Acl -LiteralPath $secret).Sddl -eq $secretBefore)
$secretBodyOk = ((Get-Content -LiteralPath $secret -Raw) -eq $secretContentBefore)
$f2p004 = ($privSddlOk -and $protFileSddlOk -and $protFileBodyOk -and $secretSddlOk -and $secretBodyOk -and ($out -match "(?<![\w])protected=2(?=[:\s]|$)"))
$outTgtSddlOk = ((Get-Acl -LiteralPath $outsideTarget).Sddl -eq $outsideTargetBefore)
$outTgtBodyOk = ((Get-Content -LiteralPath (Join-Path $outsideTarget "目标内容.txt") -Raw) -eq $outsideContentBefore)
$outFileSddlOk = ((Get-Acl -LiteralPath $outsideFile).Sddl -eq $outsideFileAclBefore)
$outFileBodyOk = ((Get-Content -LiteralPath $outsideFile -Raw) -eq $outsideFileBefore)
$f2p005 = ($outTgtSddlOk -and $outTgtBodyOk -and $outFileSddlOk -and $outFileBodyOk -and ($out -match "(?<![\w])reparse=2(?=[:\s]|$)"))
$f2p006 = ($denyGuestsRemain -and $denyBefore -eq $denyAfter -and ($ownerAfter -eq $ownerBefore) -and (Test-InheritedUsersModify $staleFile) -and (Test-NoExplicitUsersModify $staleFile))
$f2p007 = ($creatorOwnerRemains -and $attrsRemain -and ($adsBefore -eq $adsAfter) -and ($adsAfter -match "ZoneId=3") -and (Test-InheritedUsersModify $existingFile) -and (Test-InheritedUsersModify $attrFile))
# All first-run assertions above (including the newly created descendants) have
# now been evaluated. A second reconciliation cannot repair a failing first run.
$firstRunObservation = [ordered]@{
  root_ok = [bool]$f2p001; existing_ok = [bool]$f2p002
  new_descendants_inherited_before_second_run = [bool]$f2p003
  protected_ok = [bool]$f2p004; reparse_ok = [bool]$f2p005
  deny_owner_ok = [bool]$f2p006; other_state_ok = [bool]$f2p007
}
$stablePaths = @($staging, $existing, $existingFile, $staleFile, $writeOnlyFile, $broadFile, $attrFile, $private, $secret, $protectedFile, $outsideTarget, $outsideFile, $newDir, $newFile)
$beforeSecond = @{}
foreach ($path in $stablePaths) { $beforeSecond[$path] = Get-DescriptorSignature $path }
$second = Invoke-PathAclTool -Workspace $workspace -Argument $staging
$out2 = [string]$second.output
$rootRulesAfter = @(Get-UsersRules $staging | Where-Object {
  -not $_.IsInherited -and $_.InheritanceFlags.ToString() -match "ContainerInherit" -and
  $_.InheritanceFlags.ToString() -match "ObjectInherit" -and $_.PropagationFlags.ToString() -eq "None"
})
$adminsRemain = Test-IdentityPresent $staging "S-1-5-32-544" "Allow"
New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
$firstRunObservation | ConvertTo-Json | Set-Content (Join-Path $ResultsDir 'first-run-observation.json') -Encoding UTF8
$stable = $true
foreach ($path in $stablePaths) { if ((Get-DescriptorSignature $path) -cne $beforeSecond[$path]) { $stable = $false } }
$f2p008 = ($second.code -eq 0 -and $rootRulesAfter.Count -eq 1 -and @(Get-UsersRules $staging | Where-Object { -not $_.IsInherited }).Count -eq 1 -and $adminsRemain -and $stable)
$shape = Invoke-AclShapeMatrix -Workspace $workspace -FixtureRoot $fixtureRoot -ResultsDir $ResultsDir
$f2p001 = $f2p001 -and $shape.root_ok
$f2p002 = $f2p002 -and $shape.existing_ok
$f2p003 = $f2p003 -and $shape.future_ok
$f2p008 = $f2p008 -and $shape.stable
$result = [ordered]@{
  "F2P-001" = [bool]$f2p001
  "F2P-002" = [bool]$f2p002
  "F2P-003" = [bool]$f2p003
  "F2P-004" = [bool]$f2p004
  "F2P-005" = [bool]$f2p005
  "F2P-006" = [bool]$f2p006
  "F2P-007" = [bool]$f2p007
  "F2P-008" = [bool]$f2p008
}
} catch {
  throw ("FAIL_TO_PASS verifier exception: " + $_.Exception.Message + "`n" + $_.ScriptStackTrace)
}
# Do not delete junctions/symlinks here: Remove-Item on a reparse point is a
# terminating error under $ErrorActionPreference=Stop and would discard a
# successful assertion hashtable. cleanup.ps1 / SYS owns residual removal.
return ,[hashtable]$result
