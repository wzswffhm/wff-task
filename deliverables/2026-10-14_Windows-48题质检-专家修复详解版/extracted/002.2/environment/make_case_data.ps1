<#
.SYNOPSIS
  预置冻结的输入数据：案卷夹（C:\cases）与校准案卷（C:\calibration）。
  需求 5.4：非交互、幂等、显式传播退出码。
.DESCRIPTION
  本脚本只落地【输入数据】，不落地任何判据、不计算任何摘要、不写任何答案气味。
  四个案卷夹 + 两个校准案卷：MK-01 / MK-02 / MK-03 / MK-04 / MK-05 / MK-06。
  各条目的形状含义（为什么长成这样、哪一条被谁核对）登记在题包 metadata\env_check_map.md 的
  MK 段里；镜像内不保留该对照表，运行期只能看到 MK 编号。
  内容全部为固定字面量与固定种子的确定性字节，时间戳也全部为固定字面量，
  保证多次落地得到完全一致的字节与完全一致的文件时间。
.NOTES
  MK-07：MEDIA\field-recording-0001.bin 在本脚本里只落地为小占位，
  真实体积由 prepare.ps1 在运行期展开；这样镜像层里不会存进 2.2GB 数据。
  MK-08：若干 NTFS 层面的既有形状同样由 prepare.ps1 在运行期落地——实测（2026-09-08，
  Docker Engine 29.5.3 / Win11 25H2）这些形状【不能】在构建期落地：hcsshim 导出镜像层时
  会把同名硬链接拆成两个独立文件（运行期实测 FileIndex 不同、NumberOfLinks=1），
  NTFS 压缩属性也会在层导出后丢失（运行期实测 Attributes 只剩 Archive）。
  构建期落地的 200MB 稀疏文件还会让 ImportLayer 直接失败（0x3）。
  MK-09：安全属性不在本脚本里设置，由镜像构建期的独立步骤施加，本脚本对此一无所知。
  退出码：0=成功；1=数据落地失败；2=INVALID（基础设施故障）。
#>
[CmdletBinding()]
param(
    [string]$CasesRoot = 'C:\cases',
    [string]$CalibrationRoot = 'C:\calibration'
)
$ErrorActionPreference = 'Stop'
$script:NoBom = New-Object System.Text.UTF8Encoding($false)
$script:Ascii = [System.Text.Encoding]::ASCII

function Say([string]$m) { Write-Host "[case-data] $m" }

function Get-Ext([string]$p) {
    if ($p.StartsWith('\\?\')) { return $p }
    return '\\?\' + $p
}

# MK-14：第 n 个落地的文件得到一组只由 n 决定的固定时间（UTC）。
# 不用 DateTime.Now，否则同一份输入数据在不同时刻落地会得到不同的文件时间。
function Get-CreatedUtc([int]$n) {
    return ([datetime]'2024-01-01T00:00:00Z').AddMinutes(37 * $n)
}
function Get-WrittenUtc([int]$n) {
    return ([datetime]'2024-06-01T00:00:00Z').AddMinutes(53 * $n)
}

$script:Seq = 0
function Step-Seq { $script:Seq++; return $script:Seq }

function New-CaseText([string]$fullPath, [string]$text) {
    $ext = Get-Ext $fullPath
    $dir = [System.IO.Path]::GetDirectoryName($ext)
    if (-not [System.IO.Directory]::Exists($dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
    [System.IO.File]::WriteAllText($ext, $text, $script:NoBom)
    $n = Step-Seq
    [System.IO.File]::SetCreationTimeUtc($ext, (Get-CreatedUtc $n))
    [System.IO.File]::SetLastWriteTimeUtc($ext, (Get-WrittenUtc $n))
}

function New-CaseBytes([string]$fullPath, [long]$length, [int]$seed) {
    $ext = Get-Ext $fullPath
    $dir = [System.IO.Path]::GetDirectoryName($ext)
    if (-not [System.IO.Directory]::Exists($dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
    if ($length -eq 0) {
        [System.IO.File]::WriteAllBytes($ext, (New-Object 'byte[]' 0))
    } else {
        $bytes = New-Object 'byte[]' $length
        $state = $seed
        for ($i = 0; $i -lt $length; $i++) {
            $state = ($state * 1103515245 + 12345) -band 0x7FFFFFFF
            $bytes[$i] = [byte](($state -shr 16) -band 0xFF)
        }
        [System.IO.File]::WriteAllBytes($ext, $bytes)
    }
    $n = Step-Seq
    [System.IO.File]::SetCreationTimeUtc($ext, (Get-CreatedUtc $n))
    [System.IO.File]::SetLastWriteTimeUtc($ext, (Get-WrittenUtc $n))
}

function New-CaseLines([string]$fullPath, [int]$lines, [int]$seed) {
    $ext = Get-Ext $fullPath
    $dir = [System.IO.Path]::GetDirectoryName($ext)
    if (-not [System.IO.Directory]::Exists($dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
    $sb = New-Object System.Text.StringBuilder
    for ($i = 0; $i -lt $lines; $i++) {
        [void]$sb.AppendLine(('northgate transcode cache frame {0:d6} seed {1} padding padding padding' -f $i, $seed))
    }
    [System.IO.File]::WriteAllText($ext, $sb.ToString(), $script:NoBom)
    $n = Step-Seq
    [System.IO.File]::SetCreationTimeUtc($ext, (Get-CreatedUtc $n))
    [System.IO.File]::SetLastWriteTimeUtc($ext, (Get-WrittenUtc $n))
}

function New-CaseStream([string]$fullPath, [string]$streamName, [string]$text) {
    # MK-13：统一走扩展长度路径形式，短路径与超长路径都成立。
    $streamPath = (Get-Ext $fullPath) + ':' + $streamName
    [System.IO.File]::WriteAllText($streamPath, $text, $script:NoBom)
}

function Get-StreamNames([string]$fullPath) {
    return @(Get-Item -LiteralPath (Get-Ext $fullPath) -Stream * -ErrorAction SilentlyContinue | ForEach-Object { [string]$_.Stream })
}

function Get-FileCount([string]$root) {
    return @([System.IO.Directory]::GetFiles((Get-Ext $root), '*', [System.IO.SearchOption]::AllDirectories)).Count
}

function Reset-Root([string]$root) {
    $resolved = [System.IO.Path]::GetFullPath($root)
    if (-not ($resolved.StartsWith('D:\bench-runs\windows-d6-0007\', [StringComparison]::OrdinalIgnoreCase) -or $resolved.StartsWith('C:\task-state\windows-d6-0007\', [StringComparison]::OrdinalIgnoreCase))) { throw 'Input path is outside this task' }
    if ($resolved -notmatch '\\state\\(cases|calibration\\cases)$') { throw 'Input path is not a per-run fixture root' }
    $ext = Get-Ext $root
    if ([System.IO.Directory]::Exists($ext)) { Remove-Item -LiteralPath $ext -Recurse -Force }
    [System.IO.Directory]::CreateDirectory($ext) | Out-Null
}

try {
    Say ('落地案卷夹到 ' + $CasesRoot + '，校准案卷到 ' + $CalibrationRoot)
    Reset-Root $CasesRoot

    # ================= CASE-1000：普通案卷夹（回归基线） =================
    $script:Seq = 0
    $c1 = Join-Path $CasesRoot 'CASE-1000'
    New-CaseText  (Join-Path $c1 'intake\note.txt')      "Northgate intake note for CASE-1000.`r`nCustodian: records desk.`r`n"
    New-CaseText  (Join-Path $c1 'evidence\index.txt')   "photo-01.bin`r`nphoto-02.bin`r`n"
    New-CaseBytes (Join-Path $c1 'evidence\photo-01.bin') 4096 20260101
    New-CaseBytes (Join-Path $c1 'evidence\photo-02.bin') 8192 20260102
    Say ('CASE-1000 完成，文件数=' + (Get-FileCount $c1))

    # ================= CASE-2231：现场案卷夹 =================
    $script:Seq = 0
    $c2 = Join-Path $CasesRoot 'CASE-2231'
    New-CaseText (Join-Path $c2 'intake\note.txt') "Northgate intake note for CASE-2231.`r`nCustodian: field operations.`r`n"
    New-CaseText (Join-Path $c2 'names\manifest.txt') "ledger.csv`r`narchive.dat`r`npayload.bin`r`n"
    New-CaseText (Join-Path $c2 'names\ledger.csv') "seq,item,custodian`r`n1,archive.dat,field-unit-07`r`n2,payload.bin,field-unit-07`r`n"

    $archive = Join-Path $c2 'names\archive.dat'
    New-CaseBytes $archive 2048 20260231
    New-CaseStream $archive 'Northgate.Chain' 'chain-of-custody: CASE-2231; recorder=field-unit-07; handoff=records-desk; seq=0007'

    # MK-10
    New-CaseText (Join-Path $c2 'MEDIA\export-index.txt') "frame-0001.bin`r`nfield-recording-0001.bin`r`nexported-by=field-unit-07`r`n"
    New-CaseText (Join-Path $c2 'MEDIA\Zulu-frame.txt') "zulu frame marker`r`n"
    New-CaseText (Join-Path $c2 'MEDIA\alpha-frame.txt') "alpha frame marker`r`n"
    New-CaseBytes (Join-Path $c2 'MEDIA\frame-0001.bin') 3072 20260315

    # MK-07：构建期只放小占位，运行期由 prepare.ps1 展开成冻结体积。
    New-CaseBytes (Join-Path $c2 'MEDIA\field-recording-0001.bin') 4096 20260316
    New-CaseStream (Join-Path $c2 'MEDIA\field-recording-0001.bin') 'Northgate.Chain' 'chain-of-custody: CASE-2231; item=field-recording-0001; recorder=field-unit-07; duration=00:41:07'

    # MK-09：采集端交来时的既有安全属性由构建期独立步骤施加。
    $custody = Join-Path $c2 'custody\chain-01.bin'
    New-CaseBytes $custody 1536 20260420
    New-CaseStream $custody 'Northgate.Chain' 'chain-of-custody: CASE-2231; item=chain-01; custodian=records-desk; seal=0007'

    # MK-11
    New-CaseText (Join-Path $c2 'Zebra\z-note.txt') "zebra note`r`n"
    New-CaseText (Join-Path $c2 '_scratch\u-note.txt') "underscore scratch note`r`n"

    # MK-12
    $deep = Join-Path $c2 'names'
    for ($i = 0; $i -lt 12; $i++) {
        $deep = Join-Path $deep ('segment{0:d2}_{1}' -f $i, ('a' * 18))
    }
    $deepFile = Join-Path $deep 'payload.bin'
    New-CaseText $deepFile "CASE-2231 deep payload.`r`n"
    New-CaseStream $deepFile 'Northgate.Chain' 'chain-of-custody: CASE-2231; recorder=field-unit-07; handoff=records-desk; seq=0007; item=deep-payload'
    # MK-16 / MK-17：两个新条目，运行期形状由 prepare.ps1 补齐（见 MK-08）。
    New-CaseBytes (Join-Path $c2 'intake\intake-manifest.bin') 4096 20260711
    New-CaseLines (Join-Path $c2 'bulk\transcode-cache.bin') 3000 20260712
    Say ('CASE-2231 完成，文件数=' + (Get-FileCount $c2) + '，最深文件全路径长度=' + $deepFile.Length)

    # ================= CASE-2232：交接中的案卷夹 =================
    $script:Seq = 0
    $c3 = Join-Path $CasesRoot 'CASE-2232'
    New-CaseText (Join-Path $c3 'intake\note.txt') "Northgate intake note for CASE-2232.`r`nCustodian: handoff in progress.`r`n"
    New-CaseText (Join-Path $c3 'locked\manifest.txt') "inuse.bin`r`n"
    New-CaseBytes (Join-Path $c3 'locked\inuse.bin') 2048 20260501
    Say ('CASE-2232 完成，文件数=' + (Get-FileCount $c3))

    # ================= 校准案卷：CASE-0100 / CASE-0200 =================
    $script:Seq = 0
    $calCases = Join-Path $CalibrationRoot 'cases'
    if (-not [System.IO.Directory]::Exists((Get-Ext $CalibrationRoot))) { [System.IO.Directory]::CreateDirectory((Get-Ext $CalibrationRoot)) | Out-Null }
    # MK-15：只重置 cases 子树；$CalibrationRoot 里还有镜像携带的 expected.json
    Reset-Root $calCases
    $k1 = Join-Path $calCases 'CASE-0100'
    New-CaseText (Join-Path $k1 'Zebra\z-note.txt') "calibration 0100 zebra`r`n"
    New-CaseText (Join-Path $k1 '_underscore\u-note.txt') "calibration 0100 underscore`r`n"
    New-CaseText (Join-Path $k1 'alpha\a-note.txt') "calibration 0100 alpha`r`n"
    New-CaseText (Join-Path $k1 'intake\Zulu.txt') "calibration 0100 zulu`r`n"
    New-CaseText (Join-Path $k1 'intake\alpha.txt') "calibration 0100 alpha-lower`r`n"
    New-CaseText (Join-Path $k1 'MEDIA\现场记录.txt') "现场记录：校准案卷 CASE-0100。`r`n"
    $bound = Join-Path $k1 'bound\chain.dat'
    New-CaseBytes $bound 1024 20260601
    New-CaseStream $bound 'Northgate.Chain' 'calibration 0100 chain'
    New-CaseStream $bound 'Zeta.Side' 'calibration 0100 zeta'
    New-CaseStream $bound 'aaa.side' 'calibration 0100 aaa'
    Say ('CASE-0100 完成，文件数=' + (Get-FileCount $k1))

    $script:Seq = 0
    $k2 = Join-Path $calCases 'CASE-0200'
    New-CaseText (Join-Path $k2 'root.txt') "calibration 0200 root`r`n"
    New-CaseText (Join-Path $k2 'notes\readme.md') "# calibration 0200`r`n`r`nknown-good mirror`r`n"
    New-CaseBytes (Join-Path $k2 'notes\empty.bin') 0 20260602
    $leaf = Join-Path $k2 'deep\seg\leaf.bin'
    New-CaseBytes $leaf 768 20260603
    New-CaseStream $leaf 'Northgate.Chain' 'calibration 0200 leaf chain'
    $trailer = Join-Path $k2 'dupes\trailer.bin'
    New-CaseBytes $trailer 512 20260604
    New-CaseStream $trailer 'Northgate.Chain' 'calibration 0200 trailer chain'
    New-CaseStream $trailer ([string][char]0x94FE) 'calibration 0200 trailer side stream'
    Say ('CASE-0200 完成，文件数=' + (Get-FileCount $k2))

    # ================= 落地后自检：数量与关键形状 =================
    $checks = @(
        @{ name = 'MK-01 文件数=4';            ok = ((Get-FileCount (Join-Path $CasesRoot 'CASE-1000')) -eq 4) },
        @{ name = 'MK-02 文件数=15';            ok = ((Get-FileCount (Join-Path $CasesRoot 'CASE-2231')) -eq 15) },
        @{ name = 'MK-03 文件数=3';            ok = ((Get-FileCount (Join-Path $CasesRoot 'CASE-2232')) -eq 3) },
        @{ name = 'MK-05 文件数=7';            ok = ((Get-FileCount (Join-Path $calCases 'CASE-0100')) -eq 7) },
        @{ name = 'MK-06 文件数=5';            ok = ((Get-FileCount (Join-Path $calCases 'CASE-0200')) -eq 5) }
    )
    foreach ($chk in $checks) {
        if (-not $chk.ok) { Say ('[FAILED] ' + $chk.name); exit 1 }
        Say ('自检通过：' + $chk.name)
    }
    if ($deepFile.Length -le 260) { Say '[FAILED] MK-12 未满足'; exit 1 }
    Say ('自检通过：MK-12 长度=' + $deepFile.Length)

    $adsExpect = @(
        (Join-Path $c2 'names\archive.dat'),
        (Join-Path $c2 'MEDIA\field-recording-0001.bin'),
        (Join-Path $c2 'custody\chain-01.bin'),
        $deepFile
    )
    foreach ($f in $adsExpect) {
        $sn = Get-StreamNames $f
        if ($sn -notcontains 'Northgate.Chain') { Say ('[FAILED] MK-13 缺失: ' + $f + ' 实际=' + ($sn -join ',')); exit 1 }
    }
    Say ('自检通过：MK-13 计数=' + $adsExpect.Count)

    $boundStreams = Get-StreamNames $bound
    foreach ($want in @('Northgate.Chain', 'Zeta.Side', 'aaa.side')) {
        if ($boundStreams -notcontains $want) { Say ('[FAILED] MK-18 缺失 ' + $want); exit 1 }
    }
    $trailerStreams = Get-StreamNames $trailer
    if ($trailerStreams.Count -ne 3) { Say ('[FAILED] MK-19 流数应为 3，实际 ' + $trailerStreams.Count + '：' + ($trailerStreams -join ',')); exit 1 }
    Say '自检通过：MK-18 / MK-19'

    if (-not [System.IO.File]::Exists((Get-Ext (Join-Path $k1 'MEDIA\现场记录.txt')))) { Say '[FAILED] MK-20 未落地'; exit 1 }
    if (-not [System.IO.File]::Exists((Get-Ext (Join-Path $k2 'notes\empty.bin')))) { Say '[FAILED] MK-21 未落地'; exit 1 }
    if ((New-Object System.IO.FileInfo((Get-Ext (Join-Path $k2 'notes\empty.bin')))).Length -ne 0) { Say '[FAILED] MK-21 长度非 0'; exit 1 }
    Say '自检通过：MK-20 / MK-21'

    foreach ($chk2 in @(@('MK-16', (Join-Path $c2 'intake\intake-manifest.bin'), 4096), @('MK-17', (Join-Path $c2 'bulk\transcode-cache.bin'), 0))) {
        $fi = New-Object System.IO.FileInfo((Get-Ext $chk2[1]))
        if (-not $fi.Exists) { Say ('[FAILED] ' + $chk2[0] + ' 未落地'); exit 1 }
        if ($chk2[2] -gt 0 -and $fi.Length -ne $chk2[2]) { Say ('[FAILED] ' + $chk2[0] + ' 长度=' + $fi.Length); exit 1 }
        if ($chk2[2] -eq 0 -and $fi.Length -lt 100000) { Say ('[FAILED] ' + $chk2[0] + ' 长度=' + $fi.Length); exit 1 }
        Say ('自检通过：' + $chk2[0] + ' 长度=' + $fi.Length)
    }

    Say 'OK'
    exit 0
}
catch {
    Say ('[INVALID] ' + $_.Exception.Message)
    exit 2
}
