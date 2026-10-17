# probe_toolchain.ps1 -- functional probes for toolchain_in_image, run INSIDE L1 (L2 containers).
$ErrorActionPreference = 'Continue'
$ev = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\delivery-evidence-101'
New-Item -ItemType Directory -Force -Path $ev | Out-Null
$out = New-Object System.Collections.Generic.List[string]

foreach ($img in @('ghcr.io/wzswffhm/wfflab-windows:wsparse-215-1.0.1',
                   'ghcr.io/wzswffhm/wfflab-windows:wvas-216-1.0.1')) {
    $out.Add("######## $img")
    $pkgname = if ($img -match 'wsparse') { 'wsparse' } else { 'wvas' }

    $out.Add('--- os build (L2 container) ---')
    $out.Add((docker run --rm $img cmd /c ver 2>&1 | Out-String).Trim())

    $out.Add('--- git ---')
    $out.Add((docker run --rm $img cmd /c "C:\Git\cmd\git.exe --version" 2>&1 | Out-String).Trim())

    $out.Add('--- python ---')
    $out.Add((docker run --rm $img cmd /c "C:\Python312\python.exe --version" 2>&1 | Out-String).Trim())

    $out.Add('--- pip ---')
    $out.Add((docker run --rm $img cmd /c "C:\Python312\python.exe -m pip --version" 2>&1 | Out-String).Trim())

    $out.Add('--- pytest ---')
    $out.Add((docker run --rm $img cmd /c "C:\Python312\python.exe -m pytest --version" 2>&1 | Out-String).Trim())

    $out.Add('--- test modules import ---')
    $probe = 'import pytest, pytest_jsonreport, zstandard; print("modules OK", pytest.__version__)'
    $pfile = Join-Path $env:TEMP 'probe_mod.py'
    Set-Content -Path $pfile -Value $probe -Encoding ASCII
    docker cp $pfile "${img}:/probe_mod.py" 2>&1 | Out-Null
    $tmpName = 'wffprobe-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
    $out.Add((docker run --rm --name $tmpName -v "${env:TEMP}:/probe" $img cmd /c "C:\Python312\python.exe C:\probe\probe_mod.py" 2>&1 | Out-String).Trim())

    $out.Add("--- workspace import ($pkgname) ---")
    $out.Add((docker run --rm $img cmd /c "cd /d C:\testbed && C:\Python312\python.exe -c `"import $pkgname; print('import OK')\`"" 2>&1 | Out-String).Trim())

    $out.Add('--- docker image digest ---')
    $out.Add(((docker images --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}}') 2>&1 |
              Where-Object { $_ -like "*$($img)*" } | Out-String).Trim())
    $out.Add('')
}

$out | ForEach-Object { $_ }
$out | Set-Content "$ev\toolchain-probes-101.txt" -Encoding UTF8
"written -> $ev\toolchain-probes-101.txt"
