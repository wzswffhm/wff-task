# Filesystem capability probe inside a Windows container.
# Distinguishes what the bind-mounted C:\task volume supports from what the
# container-local writable layer supports.

$ErrorActionPreference = 'Continue'

function Probe {
    param([string]$Name, [scriptblock]$Body)
    try {
        $result = & $Body
        Write-Host ("[OK]   {0} -> {1}" -f $Name, ($result | Out-String).Trim())
    }
    catch {
        Write-Host ("[FAIL] {0} -> {1}" -f $Name, $_.Exception.Message)
    }
}

Write-Host ("cwd = " + (Get-Location).Path)
Write-Host ("mounted task differs from local? " + (Test-Path 'C:\task'))

# ---- inside the bind mount -------------------------------------------------
Probe 'mount: mkdir' {
    New-Item -ItemType Directory -Path 'C:\task\.probe\a' -Force | Out-Null
    'created'
}
Probe 'mount: file' {
    Set-Content -LiteralPath 'C:\task\.probe\a\target.txt' -Value 'x' -NoNewline -Encoding ASCII
    'created'
}
Probe 'mount: hardlink' {
    New-Item -ItemType HardLink -Path 'C:\task\.probe\a\hl.txt' -Target 'C:\task\.probe\a\target.txt' | Out-Null
    'created'
}
Probe 'mount: junction' {
    New-Item -ItemType Junction -Path 'C:\task\.probe\j' -Target 'C:\task\.probe\a' | Out-Null
    'created'
}
Probe 'mount: symlink(dir) via mklink /D' {
    $r = & cmd.exe /c 'cd /d C:\task\.probe && mklink /D sl a 2>&1'
    if ($LASTEXITCODE -ne 0) { throw ($r | Out-String) }
    ($r | Out-String).Trim()
}

# ---- container-local writable layer ---------------------------------------
Probe 'local: mkdir' {
    New-Item -ItemType Directory -Path 'C:\wreparse-probe\a' -Force | Out-Null
    'created'
}
Probe 'local: file' {
    Set-Content -LiteralPath 'C:\wreparse-probe\a\target.txt' -Value 'x' -NoNewline -Encoding ASCII
    'created'
}
Probe 'local: hardlink' {
    New-Item -ItemType HardLink -Path 'C:\wreparse-probe\a\hl.txt' -Target 'C:\wreparse-probe\a\target.txt' | Out-Null
    'created'
}
Probe 'local: junction' {
    New-Item -ItemType Junction -Path 'C:\wreparse-probe\j' -Target 'C:\wreparse-probe\a' | Out-Null
    'created'
}
Probe 'local: symlink(dir) via mklink /D' {
    $r = & cmd.exe /c 'cd /d C:\wreparse-probe && mklink /D sl a 2>&1'
    if ($LASTEXITCODE -ne 0) { throw ($r | Out-String) }
    ($r | Out-String).Trim()
}
Probe 'local: symlink(file) via mklink' {
    $r = & cmd.exe /c 'cd /d C:\wreparse-probe && mklink fl a\target.txt 2>&1'
    if ($LASTEXITCODE -ne 0) { throw ($r | Out-String) }
    ($r | Out-String).Trim()
}

Write-Host '--- whoami / privileges ---'
Write-Host ((& whoami) | Out-String)
Write-Host ((& whoami /priv) | Out-String)
exit 0
