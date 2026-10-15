# Confirm the rebuilt image really is the full Windows Server 2022 runtime and
# that the task prerequisites are present inside it.

$ErrorActionPreference = 'Continue'

Write-Host '--- OS identity ---'
$os = Get-CimInstance Win32_OperatingSystem
Write-Host ("Caption    : " + $os.Caption)
Write-Host ("Version    : " + $os.Version)
Write-Host ("BuildNumber: " + $os.BuildNumber)
Write-Host ("Architecture: " + $os.OSArchitecture)
Write-Host ("ProductType: " + $os.ProductType + "  (1=workstation 2=domain-controller 3=server)")

Write-Host '--- PowerShell ---'
Write-Host ("PSVersion  : " + $PSVersionTable.PSVersion)

Write-Host '--- full (untrimmed) system check ---'
foreach ($probe in @('C:\Windows\explorer.exe', 'C:\Windows\System32\mspaint.exe', 'C:\Windows\System32\notepad.exe')) {
    $ok = Test-Path -LiteralPath $probe
    Write-Host ("  {0,-42} {1}" -f $probe, $(if ($ok) { 'present' } else { 'absent' }))
}
$fontCount = @(Get-ChildItem -LiteralPath 'C:\Windows\Fonts' -File -ErrorAction SilentlyContinue).Count
Write-Host ("  C:\Windows\Fonts file count               : $fontCount")

Write-Host '--- task toolchain ---'
Write-Host ("Python     : " + (& 'C:\Python312\python.exe' --version 2>&1))
Write-Host ("pytest     : " + (& 'C:\Python312\python.exe' -m pytest --version 2>&1 | Select-Object -First 1))
Write-Host ("Git        : " + (& 'C:\Git\cmd\git.exe' --version 2>&1))
Write-Host ("workspace  : " + (Test-Path -LiteralPath 'C:\testbed\wtoken\__init__.py'))
Write-Host ("smoke test : " + (Test-Path -LiteralPath 'C:\testbed\tests\wtoken_basic.py'))
