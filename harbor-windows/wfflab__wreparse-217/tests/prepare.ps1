# Generated for wfflab__wreparse-217. Do not hand-edit the fixture layout
# without updating the checks under tests/ and the contract under docs/ together.
#
# Stage setter for every fresh run: rebuilds the fixed directory tree used by
# the WReparse checks. It never touches workspace/ (the candidate code).

[CmdletBinding()]
param(
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

# The fixture needs a hard link and relative symbolic links. When the task tree
# is projected into a Windows container through a bind mount, the container sees
# that volume through the bind filter, which rejects hard links and symbolic
# links with "Access is denied" while still allowing directories, plain files and
# junctions. The fixture therefore lives on the container's own writable layer,
# outside the task tree, so it behaves identically whether the task tree is
# mounted or copied in.
$fixtureRoot = Join-Path $env:SystemDrive 'wreparse-fixture'
$scanRoot = Join-Path $fixtureRoot 'scanroot'
$outsideRoot = Join-Path $fixtureRoot 'outside'
$prefixSibling = Join-Path $fixtureRoot 'scanroot-extra'

# Junctions make a naive recursive delete walk into their targets, so drop the
# reparse points first and only then remove the remaining tree.
function Remove-WReparseFixtureTree {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $links = @(Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint })
    foreach ($link in $links) {
        & cmd.exe /c "rmdir `"$($link.FullName)`"" | Out-Null
    }
    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
}

Remove-WReparseFixtureTree -Path $fixtureRoot

New-Item -ItemType Directory -Path (Join-Path (Join-Path $scanRoot 'docs') 'nested') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $scanRoot 'data') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $scanRoot 'beta') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $scanRoot 'empty') -Force | Out-Null

# A deliberately deep chain (8 levels) so that depth bookkeeping, the default
# -MaxDepth budget and full enumeration can all be asserted on one structure.
$deepCursor = $scanRoot
for ($i = 1; $i -le 8; $i++) {
    $deepCursor = Join-Path $deepCursor ('level' + $i)
    New-Item -ItemType Directory -Path $deepCursor -Force | Out-Null
}
Set-Content -LiteralPath (Join-Path $deepCursor 'deepest.txt') -Value 'deepest' -NoNewline -Encoding ASCII
# A second file one level above the tip, so depth counts are not trivially one.
Set-Content -LiteralPath (Join-Path (Split-Path -Parent $deepCursor) 'level8.txt') -Value 'tip' -NoNewline -Encoding ASCII
New-Item -ItemType Directory -Path $outsideRoot -Force | Out-Null
New-Item -ItemType Directory -Path $prefixSibling -Force | Out-Null

Set-Content -LiteralPath (Join-Path (Join-Path $scanRoot 'docs') 'readme.txt') -Value 'readme' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path (Join-Path (Join-Path $scanRoot 'docs') 'nested') 'deep.txt') -Value 'deep' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path (Join-Path $scanRoot 'data') 'sample.bin') -Value 'sample' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path (Join-Path $scanRoot 'beta') 'zeta.txt') -Value 'zeta' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path $scanRoot 'beta.txt') -Value 'beta' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path $scanRoot 'plain.txt') -Value 'plain' -NoNewline -Encoding ASCII

# Names whose ordinal ordering differs from their culture-aware ordering.
# The contract fixes the sort key to ordinal-ignore-case, so a host whose
# culture collates by base letter would order these differently. The names
# are built from code points so that the fixture never depends on the
# encoding of this script.
Set-Content -LiteralPath (Join-Path $scanRoot ([string][char]0x005A + '.txt')) -Value 'ascii-z' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path $scanRoot ([string][char]0x00C4 + '.txt')) -Value 'umlaut-a' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path $scanRoot ([string][char]0x00F6 + '.txt')) -Value 'umlaut-o' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path $outsideRoot 'secret.txt') -Value 'secret' -NoNewline -Encoding ASCII
Set-Content -LiteralPath (Join-Path $prefixSibling 'other.txt') -Value 'other' -NoNewline -Encoding ASCII

# A hard link shares the data stream of its target. It is a second directory
# entry, not a reparse point.
New-Item -ItemType HardLink -Path (Join-Path $scanRoot 'hardlink.txt') `
    -Target (Join-Path (Join-Path $scanRoot 'data') 'sample.bin') | Out-Null

New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-in') -Target (Join-Path $scanRoot 'docs') | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-out') -Target $outsideRoot | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-prefix') -Target $prefixSibling | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-loop') -Target $scanRoot | Out-Null
# A second junction onto the same target as link-in: revisiting a target that is
# not on the current branch's ancestry must NOT be reported as a cycle.
New-Item -ItemType Junction -Path (Join-Path $scanRoot 'link-twin') -Target (Join-Path $scanRoot 'docs') | Out-Null

# Relative symbolic links must be created through cmd.exe: New-Item in Windows
# PowerShell resolves a relative -Target against the process working directory.
$relativeLink = cmd.exe /c "cd /d `"$scanRoot`" && mklink /D link-rel docs 2>&1"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create relative symbolic link 'link-rel': $relativeLink"
}
$danglingLink = cmd.exe /c "cd /d `"$scanRoot`" && mklink /D link-dangling missing-target 2>&1"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create relative symbolic link 'link-dangling': $danglingLink"
}

# A symbolic link whose target is a FILE: with -Follow it is registered but must
# not yield any child entries.
$fileLink = cmd.exe /c "cd /d `"$scanRoot`" && mklink link-file plain.txt 2>&1"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create file symbolic link 'link-file': $fileLink"
}

$manifest = [pscustomobject][ordered]@{
    Base     = $fixtureRoot
    ScanRoot = $scanRoot
    Outside  = $outsideRoot
    Prefix   = $prefixSibling
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fixtureRoot ('fixture' + '.json')) -Encoding UTF8

Write-Host "prepare: fixture ready at $scanRoot"
exit 0
