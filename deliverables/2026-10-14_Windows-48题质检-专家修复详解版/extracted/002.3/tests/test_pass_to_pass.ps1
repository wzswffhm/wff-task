#Requires -Version 5.1
param([string]$ResultsDir = "results")
$ErrorActionPreference = "Stop"
$ConfirmPreference = "None"
$ProgressPreference = "SilentlyContinue"
$PSDefaultParameterValues["*:Confirm"] = $false
. (Join-Path $PSScriptRoot "tool_invoke.ps1")

try {
  $workspace = Get-TaskWorkspace
  if (-not (Get-PathAclDll -Workspace $workspace)) {
    if (-not (Invoke-PathAclBuild -Workspace $workspace)) { throw 'Candidate build failed.' }
  }
  $usage = Invoke-PathAclTool -Workspace $workspace
  $independent = Join-Path (Get-PathAclFixtureRoot) 'independent-new-root'
    $second = Invoke-PathAclTool -Workspace $workspace -Argument $independent
    $usersRule = $false
    if (Test-Path -LiteralPath $independent -PathType Container) {
      $usersRule = @((Get-Acl -LiteralPath $independent).Access | Where-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq 'S-1-5-32-545' -and $_.AccessControlType -eq 'Allow' -and (($_.FileSystemRights.value__ -band [int][Security.AccessControl.FileSystemRights]::Modify) -eq [int][Security.AccessControl.FileSystemRights]::Modify) }).Count -gt 0
    }
    $secondRootOk = $second.code -eq 0 -and (Test-Path $independent) -and ($second.output -match "acl-ready:") -and $usersRule
  return ,[hashtable][ordered]@{
    "P2P-001" = ($usage.code -eq 2 -and $usage.output -match "usage:")
    "P2P-002" = [bool]$secondRootOk
  }
} catch {
  throw ("PASS_TO_PASS verifier exception: " + $_.Exception.Message + "`n" + $_.ScriptStackTrace)
}
