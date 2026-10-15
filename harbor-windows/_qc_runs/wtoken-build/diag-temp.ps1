# Inspect the temporary-directory situation inside the graded container.

Write-Host '--- temp environment ---'
Write-Host ("TEMP   = " + $env:TEMP)
Write-Host ("TMP    = " + $env:TMP)
Write-Host ("TMPDIR = " + $env:TMPDIR)

Write-Host '--- candidate directory ---'
$temp = $env:TEMP
Write-Host ("exists = " + (Test-Path -LiteralPath $temp))
if (Test-Path -LiteralPath $temp) {
    $item = Get-Item -LiteralPath $temp
    Write-Host ("attributes = " + $item.Attributes)
    Write-Host ("is read-only = " + (($item.Attributes -band [System.IO.FileAttributes]::ReadOnly) -ne 0))
}

Write-Host '--- can a file be created there? ---'
try {
    $probe = Join-Path $temp 'probe-wtoken.txt'
    New-Item -ItemType File -Path $probe -Force | Out-Null
    Write-Host ("created = " + (Test-Path -LiteralPath $probe))
    Remove-Item -LiteralPath $probe -Force
}
catch {
    Write-Host ("CREATE FAILED: " + $_.Exception.Message)
}

Write-Host '--- python view of tempfile ---'
& 'C:\Python312\python.exe' -c "import tempfile, os; print('gettempdir ->', tempfile.gettempdir()); print('env TMPDIR/TEMP/TMP ->', os.environ.get('TMPDIR'), os.environ.get('TEMP'), os.environ.get('TMP')); print('cwd ->', os.getcwd()); d=tempfile.gettempdir(); f=tempfile.NamedTemporaryFile(delete=True); print('created temp file ->', f.name); f.close()"

Write-Host '--- drive space ---'
Get-PSDrive -Name C | ForEach-Object {
    Write-Host ("used = {0:N1} GB, free = {1:N1} GB" -f ($_.Used / 1GB), ($_.Free / 1GB))
}

Write-Host '--- leftover graded roots ---'
$left = @(Get-ChildItem -LiteralPath $temp -Directory -Filter 'wtoken-graded-*' -ErrorAction SilentlyContinue)
Write-Host ("count = " + $left.Count)
$left | Select-Object -First 5 | ForEach-Object { Write-Host ('  ' + $_.Name) }
