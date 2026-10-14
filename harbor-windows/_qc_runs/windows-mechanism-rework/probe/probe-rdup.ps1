# ReadDirectoryChangesW mechanism probe.
# NOTE: ASCII only. The container's Windows PowerShell 5.1 reads this file as ANSI,
# so non-ASCII bytes would break script parsing.
$ErrorActionPreference = 'Continue'

$src = @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class W {
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern IntPtr CreateFileW(string n, uint acc, uint share, IntPtr sa, uint disp, uint flags, IntPtr tpl);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadDirectoryChangesW(IntPtr h, IntPtr buf, uint len, bool sub, uint filter, out uint ret, IntPtr ov, IntPtr cr);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool MoveFileExW(string a, string b, uint f);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool DeleteFileW(string a);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern uint GetFinalPathNameByHandleW(IntPtr h, StringBuilder sb, uint cch, uint flags);
}
'@

try { Add-Type -TypeDefinition $src -Language CSharp -ErrorAction Stop }
catch { Write-Output ("ADDTYPE_FAIL: " + $_.Exception.Message); exit 9 }
Write-Output "ADDTYPE_OK"

$FILE_LIST_DIRECTORY = 1
$SHARE_ALL = 7
$SHARE_NO_DELETE = 3
$OPEN_EXISTING = 3
$BACKUP_SEMANTICS = 0x02000000
$FILTER = 0x1F

function New-ProbeDir([string]$p) {
  if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue }
  New-Item -ItemType Directory -Force $p | Out-Null
}
function Open-Dir([string]$p, [uint32]$share) {
  $h = [W]::CreateFileW($p, $FILE_LIST_DIRECTORY, $share, [IntPtr]::Zero, $OPEN_EXISTING, $BACKUP_SEMANTICS, [IntPtr]::Zero)
  if ($h.ToInt64() -eq -1 -or $h -eq [IntPtr]::Zero) { throw ("CreateFileW failed: " + [Runtime.InteropServices.Marshal]::GetLastWin32Error()) }
  return $h
}
function Get-HandlePath([IntPtr]$h) {
  $sb = New-Object System.Text.StringBuilder 1024
  $n = [W]::GetFinalPathNameByHandleW($h, $sb, 1024, 2)
  return [pscustomobject]@{ Len = $n; Path = $sb.ToString(); Err = [Runtime.InteropServices.Marshal]::GetLastWin32Error() }
}
function Read-Events([IntPtr]$h, [int]$bufSize) {
  $buf = [Runtime.InteropServices.Marshal]::AllocHGlobal($bufSize)
  try {
    $ret = [uint32]0
    $ok = [W]::ReadDirectoryChangesW($h, $buf, [uint32]$bufSize, $true, $FILTER, [ref]$ret, [IntPtr]::Zero, [IntPtr]::Zero)
    $err = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    $ev = New-Object System.Collections.ArrayList
    if ($ok -and $ret -gt 0) {
      $off = 0
      while ($true) {
        $next = [Runtime.InteropServices.Marshal]::ReadInt32($buf, $off)
        $act  = [Runtime.InteropServices.Marshal]::ReadInt32($buf, $off + 4)
        $len  = [Runtime.InteropServices.Marshal]::ReadInt32($buf, $off + 8)
        $nm   = [Runtime.InteropServices.Marshal]::PtrToStringUni([IntPtr]::Add($buf, $off + 12), [int]($len / 2))
        [void]$ev.Add(("{0}:{1}" -f $act, $nm))
        if ($next -eq 0) { break }
        $off += $next
      }
    }
    return [pscustomobject]@{ Ok = $ok; Bytes = [int]$ret; Err = $err; Events = $ev }
  } finally {
    [Runtime.InteropServices.Marshal]::FreeHGlobal($buf)
  }
}

$root = 'C:\probe\w'

Write-Output ""
Write-Output "===== A. rename: MoveFileExW(a.txt -> b.txt) ====="
New-ProbeDir $root
[IO.File]::WriteAllText("$root\a.txt", 'aa')
$h = Open-Dir $root $SHARE_ALL
[void][W]::MoveFileExW("$root\a.txt", "$root\b.txt", 0)
$r = Read-Events $h 4096
Write-Output ("ok={0} bytes={1} err={2} n={3}" -f $r.Ok, $r.Bytes, $r.Err, $r.Events.Count)
$r.Events | ForEach-Object { Write-Output ("  " + $_) }
[void][W]::CloseHandle($h)

Write-Output ""
Write-Output "===== A2. rename into subdirectory ====="
New-ProbeDir $root
New-Item -ItemType Directory -Force "$root\sub" | Out-Null
[IO.File]::WriteAllText("$root\c.txt", 'cc')
$h = Open-Dir $root $SHARE_ALL
[void][W]::MoveFileExW("$root\c.txt", "$root\sub\c.txt", 0)
$r = Read-Events $h 4096
Write-Output ("ok={0} bytes={1} err={2} n={3}" -f $r.Ok, $r.Bytes, $r.Err, $r.Events.Count)
$r.Events | ForEach-Object { Write-Output ("  " + $_) }
[void][W]::CloseHandle($h)

Write-Output ""
Write-Output "===== B. delete + recreate same name (polling cannot tell from rename) ====="
New-ProbeDir $root
[IO.File]::WriteAllText("$root\x.txt", 'aa')
$h = Open-Dir $root $SHARE_ALL
[void][W]::DeleteFileW("$root\x.txt")
[IO.File]::WriteAllText("$root\x.txt", 'bb')
$r = Read-Events $h 4096
Write-Output ("ok={0} bytes={1} err={2} n={3}" -f $r.Ok, $r.Bytes, $r.Err, $r.Events.Count)
$r.Events | ForEach-Object { Write-Output ("  " + $_) }
[void][W]::CloseHandle($h)

foreach ($bs in 2048, 8192, 64000) {
  Write-Output ""
  Write-Output ("===== C. overflow: buffer={0} bytes, 500 files created at once =====" -f $bs)
  New-ProbeDir $root
  $h = Open-Dir $root $SHARE_ALL
  1..500 | ForEach-Object { [IO.File]::WriteAllText("$root\g$_.txt", 'x') }
  $r = Read-Events $h $bs
  Write-Output ("read#1: ok={0} bytes={1} err={2} n={3}" -f $r.Ok, $r.Bytes, $r.Err, $r.Events.Count)
  $r.Events | Select-Object -First 3 | ForEach-Object { Write-Output ("  " + $_) }
  $r2 = Read-Events $h $bs
  Write-Output ("read#2: ok={0} bytes={1} err={2} n={3}" -f $r2.Ok, $r2.Bytes, $r2.Err, $r2.Events.Count)
  $r2.Events | Select-Object -First 3 | ForEach-Object { Write-Output ("  " + $_) }
  [void][W]::CloseHandle($h)
}

Write-Output ""
Write-Output "===== D. watched directory itself moved away (GetFinalPathNameByHandleW) ====="
New-ProbeDir $root
New-Item -ItemType Directory -Force "$root\inner" | Out-Null
$h = Open-Dir "$root\inner" $SHARE_ALL
$before = Get-HandlePath $h
Write-Output ("before move: len={0} path={1}" -f $before.Len, $before.Path)
[void][W]::MoveFileExW("$root\inner", "$root\moved", 0)
Start-Sleep -Milliseconds 300
$after = Get-HandlePath $h
Write-Output ("after  move: len={0} path={1}" -f $after.Len, $after.Path)
Write-Output ("path changed => {0}" -f ($before.Path -ne $after.Path))
$r = Read-Events $h 4096
Write-Output ("post-move read: ok={0} bytes={1} err={2} n={3}" -f $r.Ok, $r.Bytes, $r.Err, $r.Events.Count)
$r.Events | ForEach-Object { Write-Output ("  " + $_) }
$r3 = Read-Events $h 4096
Write-Output ("post-move read#2: ok={0} bytes={1} err={2} n={3}" -f $r3.Ok, $r3.Bytes, $r3.Err, $r3.Events.Count)
[void][W]::CloseHandle($h)

Write-Output ""
Write-Output "===== E. directory handle without FILE_SHARE_DELETE vs moving that directory ====="
New-ProbeDir $root
New-Item -ItemType Directory -Force "$root\inner2" | Out-Null
$h = Open-Dir "$root\inner2" $SHARE_NO_DELETE
$mv = [W]::MoveFileExW("$root\inner2", "$root\moved2", 0)
$mverr = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
Write-Output ("move while handle open (no share delete): ok={0} err={1} (32=ERROR_SHARING_VIOLATION)" -f $mv, $mverr)
[void][W]::CloseHandle($h)
$mv2 = [W]::MoveFileExW("$root\inner2", "$root\moved2", 0)
Write-Output ("move after close: ok={0}" -f $mv2)

Write-Output ""
Write-Output "PROBE_DONE"
