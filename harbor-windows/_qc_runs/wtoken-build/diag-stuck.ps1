# Inspect a stuck Harbor verifier container.
# Run inside the container to see whether anything is still executing.

Write-Output '--- processes ---'
Get-Process | Where-Object { $_.ProcessName -match 'python|pytest|powershell|cmd' } |
    Select-Object ProcessName, Id, CPU, StartTime |
    Format-Table -AutoSize | Out-String -Width 200

Write-Output '--- verifier script present? ---'
foreach ($p in @('C:\tests\run_tests.ps1', 'C:\tests\tests\test_wtoken_semantics.py')) {
    Write-Output ("  {0} : {1}" -f $p, (Test-Path -LiteralPath $p))
}

Write-Output '--- verifier outputs so far ---'
foreach ($d in @('C:\verifier', 'C:\tests')) {
    if (Test-Path -LiteralPath $d) {
        Get-ChildItem -LiteralPath $d -File -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Output ("  {0}\{1}  {2} B" -f $d, $_.Name, $_.Length)
        }
    }
}

Write-Output '--- temp dirs (grading workspace) ---'
$tmp = 'C:\Users\ContainerAdministrator\AppData\Local\Temp'
if (Test-Path -LiteralPath $tmp) {
    Get-ChildItem -LiteralPath $tmp -Directory -ErrorAction SilentlyContinue |
        Select-Object -First 10 | ForEach-Object { Write-Output ("  " + $_.Name) }
}
