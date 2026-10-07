# Probe: does Windows PowerShell 5.1 expose LinkType / Target / ResolvedTarget for reparse points?
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:TEMP 'wreparse-probe51'
Remove-Item $base -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $base | Out-Null
$real = Join-Path $base 'realdir'
New-Item -ItemType Directory -Path $real | Out-Null
Set-Content -Path (Join-Path $real 'a.txt') -Value 'hello'

$j = Join-Path $base 'junc'
New-Item -ItemType Junction -Path $j -Target $real | Out-Null

$out = @()
$out += "PSVersion=$($PSVersionTable.PSVersion) Edition=$($PSVersionTable.PSEdition)"
foreach ($p in @($base, $real, $j, (Join-Path $real 'a.txt'))) {
  $i = Get-Item -LiteralPath $p -Force
  $out += "PATH=$($i.FullName)"
  $out += "  Attributes=$($i.Attributes)"
  $out += "  LinkType=[$($i.LinkType)]"
  $out += "  Target=[$($i.Target)]"
  $hasRT = $null -ne $i.PSObject.Properties['ResolvedTarget']
  $out += "  HasResolvedTarget=$hasRT"
  if ($hasRT) { $out += "  ResolvedTarget=[$($i.ResolvedTarget)]" }
  $out += "  Type=$($i.GetType().FullName)"
}

# relative symbolic link
$sl = Join-Path $base 'rel-sym'
try {
  New-Item -ItemType SymbolicLink -Path $sl -Target 'realdir' | Out-Null
  $i = Get-Item -LiteralPath $sl -Force
  $out += "REL-SYM LinkType=[$($i.LinkType)] Target=[$($i.Target)]"
} catch {
  $out += "REL-SYM failed: $($_.Exception.Message)"
}

# hard link
$hl = Join-Path $base 'hard-a.txt'
try {
  New-Item -ItemType HardLink -Path $hl -Target (Join-Path $real 'a.txt') | Out-Null
  $i = Get-Item -LiteralPath $hl -Force
  $out += "HARDLINK LinkType=[$($i.LinkType)] Target=[$($i.Target)]"
} catch {
  $out += "HARDLINK failed: $($_.Exception.Message)"
}

# broken (dangling) symlink
$dang = Join-Path $base 'dangling'
try {
  New-Item -ItemType SymbolicLink -Path $dang -Target (Join-Path $base 'nonexistent') | Out-Null
  $i = Get-Item -LiteralPath $dang -Force
  $out += "DANGLING exists(Test-Path)=$(Test-Path -LiteralPath $dang) LinkType=[$($i.LinkType)] Target=[$($i.Target)]"
} catch {
  $out += "DANGLING failed: $($_.Exception.Message)"
}

Remove-Item $base -Recurse -Force -ErrorAction SilentlyContinue
$out -join "`n"
