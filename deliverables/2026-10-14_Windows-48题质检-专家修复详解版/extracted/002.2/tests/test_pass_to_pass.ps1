<#
.SYNOPSIS
  PASS_TO_PASS 回归断言（需求 4.3 / 4.6.2）。初始态与参考解都必须通过。
.DESCRIPTION
  保护既有正确行为：普通案卷夹的封存语义、32 位采集宿主的加载契约、以及命令行对
  “案卷夹不存在”的干净拒绝。这些行为在初始缺陷态就是对的，修复不得把它们弄坏。
.NOTES
  共享辅助函数（NG-*）由 test_fail_to_pass.ps1 定义；判分入口 run_tests.ps1 会先点源该文件。
#>

function Test-P2P_PlainCaseFolderSealsCorrectly {
    $caseId = 'CASE-1000'
    $source = Join-Path $script:NG_Cases $caseId
    if (-not [System.IO.Directory]::Exists((NG-Ext $source))) { throw "[INVALID] 普通案卷夹缺失：$source" }
    if (-not (Test-Path -LiteralPath $script:NG_EXE)) { throw "被测产物缺失或未构建：$script:NG_EXE" }
    $dest = NG-Reset $caseId
    $run = NG-RunSeal -CaseId $caseId -Source $source -Dest $dest
    $out = $run.Lines
    $code = $run.Code
    $map = NG-MapOutput $out
    if ($code -ne 0) { throw "普通案卷夹 seal 退出码 $code，期望 0；输出：$(($out | ForEach-Object { [string]$_ }) -join ' ')" }
    $srcRels = NG-RelativeFiles $source
    if ($srcRels.Count -lt 1) { throw '[INVALID] 普通案卷夹 CASE-1000 为空（冻结输入被破坏）' }
    $mirRels = NG-RelativeFiles $dest
    $missing = @($srcRels | Where-Object { $mirRels -notcontains $_ })
    $extra   = @($mirRels | Where-Object { $srcRels -notcontains $_ })
    if ($missing.Count -gt 0 -or $extra.Count -gt 0) {
        throw "普通案卷夹镜像文件集合不一致：缺失 [$($missing -join ', ')] 多余 [$($extra -join ', ')]"
    }
    if (-not $map.ContainsKey('FileCount') -or (NG-CountValue $map['FileCount']) -ne $srcRels.Count) {
        throw "普通案卷夹 FileCount=$($map['FileCount'])，期望 $($srcRels.Count)"
    }
    $srcExt = NG-Ext $source; $mirExt = NG-Ext $dest
    foreach ($rel in $srcRels) {
        if ((NG-HashFile ($srcExt + '\' + $rel)) -ne (NG-HashFile ($mirExt + '\' + $rel))) { throw "普通案卷夹镜像文件内容与源不一致：$rel" }
    }
    # P2P protects CLI shape and ordinary file semantics. The F2P calibration
    # group separately verifies the public digest protocol on CASE-1000.
    if (-not $map.ContainsKey('RootHash') -or ([string]$map['RootHash']) -cnotmatch '^[0-9a-f]{64}$') {
        throw "普通案卷夹 RootHash 行形状不对：$($map['RootHash'])（契约要求 64 位小写十六进制）"
    }
    if (-not $map.ContainsKey('MirrorRoot') -or ([string]$map['MirrorRoot']) -cne $dest) {
        throw "普通案卷夹 MirrorRoot=$($map['MirrorRoot'])，与调用时传入的 --dest [$dest] 不逐字符相同"
    }
}

function Test-P2P_CollectorRemains32Bit {
    if (-not (Test-Path -LiteralPath $script:NG_EXE)) { throw "被测产物缺失或未构建：$script:NG_EXE" }
    $bytes = [System.IO.File]::ReadAllBytes($script:NG_EXE)
    if ($bytes.Length -lt 64) { throw "被测产物不是有效的 PE 映像（长度 $($bytes.Length)）" }
    $peOffset = [System.BitConverter]::ToInt32($bytes, 60)
    $machine = [System.BitConverter]::ToUInt16($bytes, $peOffset + 4)
    $optional = $peOffset + 24
    if ([BitConverter]::ToUInt16($bytes, $optional) -ne 0x10B) { throw 'Expected PE32 optional header' }
    $cliRva = [BitConverter]::ToUInt32($bytes, $optional + 96 + 14 * 8)
    $sectionCount = [BitConverter]::ToUInt16($bytes, $peOffset + 6)
    $sectionStart = $optional + [BitConverter]::ToUInt16($bytes, $peOffset + 20)
    $cliOffset = -1
    for ($sectionIndex = 0; $sectionIndex -lt $sectionCount; $sectionIndex++) {
        $section = $sectionStart + 40 * $sectionIndex
        $rva = [BitConverter]::ToUInt32($bytes, $section + 12)
        $size = [BitConverter]::ToUInt32($bytes, $section + 16)
        if ($cliRva -ge $rva -and $cliRva -lt ($rva + $size)) { $cliOffset = $cliRva - $rva + [BitConverter]::ToUInt32($bytes, $section + 20) }
    }
    if ($cliOffset -lt 0 -or ([BitConverter]::ToUInt32($bytes, $cliOffset + 16) -band 2) -eq 0) { throw 'CLR 32BITREQUIRED flag is missing; AnyCPU is not x86' }
    if ($machine -ne 0x014C) {
        throw ("被测产物不是 32 位（PE Machine=0x{0:X4}，期望 0x014C=x86）；采集宿主 Northgate.Collector.exe 是 32 位进程，插件产物必须保持 x86，改成 64 位会破坏加载契约" -f $machine)
    }
}

function Test-P2P_CliRejectsMissingSourceCleanly {
    $caseId = 'CASE-9999'
    $missingSource = Join-Path $script:NG_Cases 'DOES-NOT-EXIST-9999'
    if (-not (Test-Path -LiteralPath $script:NG_EXE)) { throw "被测产物缺失或未构建：$script:NG_EXE" }
    $dest = NG-Reset $caseId
    $run = NG-RunSeal -CaseId $caseId -Source $missingSource -Dest $dest
    $out = $run.Lines
    $code = $run.Code
    $text = (($out | ForEach-Object { [string]$_ }) -join ' ')
    if ($code -eq 0) { throw "案卷夹不存在时 seal 仍以退出码 0 结束（应如实报错为非 0）；输出：$text" }
    if ([System.IO.Directory]::Exists((NG-Ext $dest))) { throw "案卷夹不存在时不应创建输出目录，但 $dest 被创建了" }
    foreach ($view in @('Registry64', 'Registry32')) {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', $view)
        $k = $base.OpenSubKey(($env:EVIDENCE_MIRROR_REGISTRY_ROOT + '\Cases\') + $caseId)
        if ($null -ne $k) { $k.Close(); throw "案卷夹不存在时不应写入封存记录，但 $view 视图里出现了 $caseId" }
    }
}
