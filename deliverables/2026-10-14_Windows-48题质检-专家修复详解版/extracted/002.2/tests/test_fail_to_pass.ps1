<#
.SYNOPSIS
  FAIL_TO_PASS 断言（需求 4.3 / 4.6.2）。初始缺陷态必须全部失败，参考解必须全部通过。
.DESCRIPTION
  被测产物：C:\workspace\bin\EvidenceMirror.exe（32 位采集宿主插件）。
  冻结只读输入：
    C:\cases\CASE-2231  现场案卷夹（16 个文件：>260 字符深层文件、4 个带 NTFS 附加数据流的文件、
                        2 个带外部所有者与受保护 DACL 的文件、3 个带既有审计规则(SACL)的文件、
                        1 个 2.2GB 稀疏现场录像（实际只占 64KB）、1 个 NTFS 压缩文件、
                        1 对指向同一份数据的硬链接名、大小写与下划线混排的目录名、固定的冻结时间戳）
    C:\cases\CASE-2232  交接中的案卷夹（判分时把其中一个文件独占打开，制造中途失败）
    C:\calibration      校准案卷 + 监控台已归档的已知良好封存记录
  每条断言都：清空 staging 与注册表两个视图 -> 亲自调用被测 exe 完成 seal -> 对可观测结果断言。
  这样即便 Agent 预置了 staging/注册表，也无法绕过“产物本身是否真的修好”的检验（抗篡改）。
.RULES
  - 断言名与 rubric.json 的 test_id 完全一致
  - 摘要一律由判分侧独立实现重算，不复用被测代码
  - 只读输入被破坏等基础设施故障 throw '[INVALID] ...'；被测行为不符 throw 事实性说明（不得泄露解法）
.NOTES
  本文件默认对 Agent 隐藏，只在判分阶段注入 C:\tests。共享辅助函数供本套与 P2P/SYS 复用。
#>

$script:NG_EXE = $env:EVIDENCE_MIRROR_EXE
. (Join-Path $PSScriptRoot 'candidate_contract.ps1')
$script:NG_Cases = Join-Path $env:EVIDENCE_MIRROR_STATE 'cases'
$script:NG_Stage = Join-Path $env:EVIDENCE_MIRROR_STATE 'staging'
$script:NG_Field = 'CASE-2231'
$script:NG_Atomic = 'CASE-2232'
$script:NG_Calibration = Join-Path $env:EVIDENCE_MIRROR_STATE 'calibration'
$script:NG_TrueCount = 16
$script:NG_RecordingRelative = 'MEDIA\field-recording-0001.bin'
$script:NG_RecordingBytes = 2200000000
$script:NG_ForeignOwner = 'S-1-5-21-100-200-300-1001'
$script:NG_SparseAllocatedCeiling = 4194304
$script:NG_LinkPrimaryRelative = 'intake\intake-manifest.bin'
$script:NG_LinkAliasRelative = 'names\intake-manifest.bin'
$script:NG_CompressedRelative = 'bulk\transcode-cache.bin'
$script:NG_AuditRelatives = @('names\archive.dat', 'custody\chain-01.bin', 'MEDIA\frame-0001.bin')

# 判分侧的 Win32 读数（流名的 NTFS 原始形式、实际占用大小、文件标识）统一由这段 C# 提供。
# 容器基座的 Windows PowerShell 5.1 不支持 Add-Type -MemberDefinitions，只支持 -TypeDefinition
# （实测 2026-09-08）。这段代码只随判分阶段注入的 C:\tests 进来，Agent 看不到。
$script:NG_NativeSource = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class NgNative {
    [StructLayout(LayoutKind.Sequential)] public struct BHFI { public uint FileAttributes; public uint CreationTimeLow; public uint CreationTimeHigh; public uint LastAccessTimeLow; public uint LastAccessTimeHigh; public uint LastWriteTimeLow; public uint LastWriteTimeHigh; public uint VolumeSerialNumber; public uint FileSizeHigh; public uint FileSizeLow; public uint NumberOfLinks; public uint FileIndexHigh; public uint FileIndexLow; }
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)] static extern IntPtr FindFirstStreamW(string f, int lvl, IntPtr d, uint flags);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool FindNextStreamW(IntPtr h, IntPtr d);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool FindClose(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true, EntryPoint = "GetCompressedFileSizeW", CharSet = CharSet.Unicode)] static extern uint GetCompressedFileSizeN(string f, out uint high);
    [DllImport("kernel32.dll", SetLastError = true, EntryPoint = "CreateFileW", CharSet = CharSet.Unicode)] static extern IntPtr CreateFileN(string n, uint a, uint s, IntPtr sa, uint d, uint f, IntPtr t);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool GetFileInformationByHandle(IntPtr h, out BHFI i);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);
    const int StreamDataOffset = 8;
    static readonly int StreamDataSize = 8 + ((260 + 36) * 2) + 8;
    public static string[] PublishedStreamNames(string extendedPath) {
        List<string> names = new List<string>();
        byte[] buffer = new byte[StreamDataSize];
        GCHandle pinned = GCHandle.Alloc(buffer, GCHandleType.Pinned);
        try {
            IntPtr data = pinned.AddrOfPinnedObject();
            IntPtr handle = FindFirstStreamW(extendedPath, 0, data, 0);
            if (handle == new IntPtr(-1)) { int error = Marshal.GetLastWin32Error(); if (error != 38) throw new System.ComponentModel.Win32Exception(error); names.Add(":$DATA"); return names.ToArray(); }
            try { do { names.Add(Publish(buffer)); } while (FindNextStreamW(handle, data)); int error = Marshal.GetLastWin32Error(); if (error != 38) throw new System.ComponentModel.Win32Exception(error); }
            finally { FindClose(handle); }
        } finally { pinned.Free(); }
        if (names.Count == 0) { names.Add(":$DATA"); }
        string[] arr = names.ToArray();
        Array.Sort(arr, StringComparer.Ordinal);
        return arr;
    }
    static string Publish(byte[] buffer) {
        string raw = Marshal.PtrToStringUni(Marshal.UnsafeAddrOfPinnedArrayElement(buffer, StreamDataOffset)) ?? string.Empty;
        if (raw.StartsWith(":", StringComparison.Ordinal)) { raw = raw.Substring(1); }
        return raw;
    }
    public static long AllocatedOf(string path) { uint high; uint low = GetCompressedFileSizeN(path, out high); if (low == 0xFFFFFFFF) { return -(long)Marshal.GetLastWin32Error(); } return (long)(((ulong)high << 32) | low); }
    public static string IdOf(string path) { IntPtr h = CreateFileN(path, 0x80, 3, IntPtr.Zero, 3, 0x02000000, IntPtr.Zero); if (h == new IntPtr(-1)) { return "OPENFAIL:" + Marshal.GetLastWin32Error(); } BHFI i; bool ok = GetFileInformationByHandle(h, out i); CloseHandle(h); if (!ok) { return "INFOFAIL:" + Marshal.GetLastWin32Error(); } return i.VolumeSerialNumber.ToString() + ":" + (((ulong)i.FileIndexHigh << 32) | i.FileIndexLow).ToString() + ":" + i.NumberOfLinks.ToString(); }
}
'@
if (-not ('NgNative' -as [type])) {
    try { Add-Type -TypeDefinition $script:NG_NativeSource -Language CSharp }
    catch { throw ('[INVALID] 判分侧 Win32 辅助类型编译失败：' + $_.Exception.Message) }
}

function NG-Ext([string]$p) {
    if ($p.StartsWith('\\?\')) { return $p }
    return '\\?\' + $p
}

function NG-Sha256Hex([byte[]]$bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ((($sha.ComputeHash($bytes)) | ForEach-Object { $_.ToString('x2') }) -join '') }
    finally { $sha.Dispose() }
}

# 一律走流式：现场录像有 2.2GB，判分侧自己也不许把它整体读进内存。
function NG-HashFile([string]$fullExt) {
    $fs = [System.IO.File]::Open($fullExt, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $b = $sha.ComputeHash($fs)
            return (($b | ForEach-Object { $_.ToString('x2') }) -join '')
        } finally { $sha.Dispose() }
    } finally { $fs.Close() }
}

# 摘要文本里发布的流名 = NTFS 自己报告的名字去掉最前面那个分隔冒号：主数据流是 ':$DATA'，
# 附加数据流是 '<流名>:$DATA'。PowerShell 的 -Stream 会把 ':$DATA' 类型后缀吃掉，
# 所以这里一律走 FindFirstStreamW 读原始形式（见 NgNative），不用 Get-Item -Stream。
function NG-StreamNames([string]$fullExt) {
    return [NgNative]::PublishedStreamNames($fullExt)
}

function NG-StreamPath([string]$fullExt, [string]$publishedName) {
    if ($publishedName -eq ':$DATA') { return $fullExt }
    return $fullExt + ':' + $publishedName
}

function NG-FileDigest([string]$fullExt) {
    $names = @(NG-StreamNames $fullExt)
    [System.Array]::Sort($names, [System.StringComparer]::Ordinal)
    $sb = New-Object System.Text.StringBuilder
    foreach ($n in $names) {
        [void]$sb.Append($n); [void]$sb.Append('|')
        [void]$sb.Append((NG-HashFile (NG-StreamPath $fullExt $n))); [void]$sb.Append("`n")
    }
    return (NG-Sha256Hex ([System.Text.Encoding]::UTF8.GetBytes($sb.ToString())))
}

function NG-AllocatedBytes([string]$fullExt) {
    $a = [NgNative]::AllocatedOf($fullExt)
    if ($a -lt 0) { throw ('[INVALID] 读取实际占用大小失败：' + $fullExt + ' Win32=' + (-$a)) }
    return $a
}

function NG-FileIdentity([string]$fullExt) {
    $id = [NgNative]::IdOf($fullExt)
    if ($id -like '*FAIL*') { throw ('[INVALID] 读取文件标识失败：' + $fullExt + ' ' + $id) }
    return $id
}

function NG-SaclFingerprint([string]$fullExt) {
    $sec = [System.IO.File]::GetAccessControl($fullExt, [System.Security.AccessControl.AccessControlSections]::Audit)
    $rules = @($sec.GetAuditRules($true, $true, [System.Security.Principal.SecurityIdentifier]) | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value, [int]$_.FileSystemRights, [int]$_.AuditFlags, [int]$_.InheritanceFlags, [int]$_.PropagationFlags, $_.IsInherited
    } | Sort-Object)
    return ([bool]$sec.AreAuditRulesProtected).ToString() + '#' + ($rules -join ';')
}

function NG-RelativeFiles([string]$root) {
    $ext = NG-Ext $root
    if (-not [System.IO.Directory]::Exists($ext)) { return @() }
    $files = [System.IO.Directory]::GetFiles($ext, '*', [System.IO.SearchOption]::AllDirectories)
    $rels = New-Object 'System.Collections.Generic.List[string]'
    foreach ($f in $files) { $rels.Add($f.Substring($ext.Length + 1)) }
    $arr = $rels.ToArray()
    [System.Array]::Sort($arr, [System.StringComparer]::Ordinal)
    return $arr
}

# 判分侧独立实现的摘要推导：与 C:\calibration\expected.json 里监控台归档的值同源，
# 本套在用它判分之前会先拿它把归档值复现一遍（见 Test-F2P_BuildReproducesCalibrationRecords）。
function NG-RootHash([string]$root) {
    $ext = NG-Ext $root
    $rels = NG-RelativeFiles $root
    $sb = New-Object System.Text.StringBuilder
    foreach ($r in $rels) {
        [void]$sb.Append($r); [void]$sb.Append('|')
        [void]$sb.Append((NG-FileDigest ($ext + '\' + $r))); [void]$sb.Append("`n")
    }
    return (NG-Sha256Hex ([System.Text.Encoding]::UTF8.GetBytes($sb.ToString())))
}

function NG-SdFingerprint([string]$fullExt) {
    $sections = [System.Security.AccessControl.AccessControlSections]::Owner -bor
                [System.Security.AccessControl.AccessControlSections]::Access
    $sec = [System.IO.File]::GetAccessControl($fullExt, $sections)
    $owner = $sec.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
    $protected = [bool]$sec.AreAccessRulesProtected
    $descriptor = [Security.AccessControl.RawSecurityDescriptor]::new($sec.GetSecurityDescriptorBinaryForm(), 0)
    return ($owner + '#' + $protected + '#' + (NG-DaclBlocks $descriptor.DiscretionaryAcl))
}

function NG-ClearRegistry() {
    foreach ($view in @('Registry64', 'Registry32')) {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', $view)
        try { $base.DeleteSubKeyTree($env:EVIDENCE_MIRROR_REGISTRY_ROOT, $false) } finally { $base.Dispose() }
    }
}

function NG-Reset([string]$caseId) {
    $dest = Join-Path $script:NG_Stage $caseId
    if ([System.IO.Directory]::Exists((NG-Ext $dest))) {
        $resolved = [IO.Path]::GetFullPath($dest)
        if (-not $resolved.StartsWith(([IO.Path]::GetFullPath($script:NG_Stage) + '\'), [StringComparison]::OrdinalIgnoreCase)) {throw '[INVALID] Unsafe reset path'}
        Remove-Item -LiteralPath (NG-Ext $dest) -Recurse -Force
    }
    NG-ClearRegistry
    return $dest
}

function NG-MapOutput($lines) {
    $map = @{}
    foreach ($line in $lines) {
        $s = [string]$line; $eq = $s.IndexOf('=')
        if ($eq -gt 0) { $map[$s.Substring(0, $eq)] = $s.Substring($eq + 1) }
    }
    return $map
}

# 被测 exe / reg.exe 会把诊断信息写到 stderr。判分入口 run_tests.ps1 设了
# $ErrorActionPreference='Stop'，而 Windows PowerShell 5.1 在用 2>&1 重定向原生命令时，
# 会把 stderr 行升级成终止性 NativeCommandError，让断言以“被测程序自己打印的报错文本”异常收场，
# 而不是按可观测事实判定（Evaluator 故障被伪装成测试失败，违反需求 4.3）。
# 这里在函数作用域内把 EAP 临时降为 Continue，只影响本次原生调用，不改动判分入口自身的错误策略。
function NG-RunNative {
    param([string]$FilePath,[string[]]$Arguments)
    $startInfo=New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName=$FilePath
    $startInfo.Arguments=(@($Arguments | ForEach-Object {'"'+$_+'"'}) -join ' ')
    $startInfo.UseShellExecute=$false
    $startInfo.CreateNoWindow=$true
    $startInfo.RedirectStandardOutput=$true
    $startInfo.RedirectStandardError=$true
    foreach ($name in @('BENCH_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')) {$startInfo.EnvironmentVariables.Remove($name)}
    $process=New-Object Diagnostics.Process
    $process.StartInfo=$startInfo
    if (-not $process.Start()) {throw '[INVALID] Candidate launch failed'}
    $stdout=$process.StandardOutput.ReadToEndAsync()
    $stderr=$process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(240000)) {
        $process.Kill()
        $process.WaitForExit()
        throw '[INVALID] Candidate timeout without a normal completion receipt'
    }
    if (-not [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout,$stderr),5000)) {throw '[INVALID] Incomplete output receipt'}
    $code=$process.ExitCode
    $identifier=[guid]::NewGuid().ToString('N')
    $receipt=@{file=$FilePath;arguments=$Arguments;exit_code=$code;exited=$process.HasExited;stdout=$stdout.Result;stderr=$stderr.Result}
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $env:EVIDENCE_MIRROR_RESULTS ('artifacts\'+$identifier+'.receipt.json')) -Encoding UTF8
    $lines=@($stdout.Result -split '\r?\n' | Where-Object {$_ -ne ''})
    $text=$stdout.Result+$stderr.Result
    $process.Dispose()
    return [pscustomobject]@{Code=$code;Lines=$lines;Text=$text}
}

function NG-RunSeal {
    param([string]$CaseId, [string]$Source, [string]$Dest)
    return NG-RunNative -FilePath $script:NG_EXE -Arguments @('seal', '--case', $CaseId, '--source', $Source, '--dest', $Dest)
}

function NG-RequireExe() {
    if (-not (Test-Path -LiteralPath $script:NG_EXE)) { throw "被测产物缺失或未构建：$script:NG_EXE" }
}

function NG-RequireSource() {
    $source = Join-Path $script:NG_Cases $script:NG_Field
    if (-not [System.IO.Directory]::Exists((NG-Ext $source))) { throw "[INVALID] 只读案卷夹缺失：$source" }
    NG-RequireExe
    return $source
}

function NG-RequireFieldShape() {
    $source = Join-Path $script:NG_Cases $script:NG_Field
    $count = ([System.IO.Directory]::GetFiles((NG-Ext $source), '*', [System.IO.SearchOption]::AllDirectories)).Count
    if ($count -ne $script:NG_TrueCount) { throw "[INVALID] 现场案卷夹真实文件数=$count，期望 $($script:NG_TrueCount)（冻结输入形状异常）" }
    $rec = NG-Ext (Join-Path $source $script:NG_RecordingRelative)
    if (-not [System.IO.File]::Exists($rec)) { throw '[INVALID] 现场录像文件缺失（冻结输入被破坏）' }
    $len = (New-Object System.IO.FileInfo($rec)).Length
    if ($len -ne $script:NG_RecordingBytes) { throw "[INVALID] 现场录像体积=$len，期望 $($script:NG_RecordingBytes)（prepare 未把它展开成冻结体积）" }
    $foreign = 0
    foreach ($f in [System.IO.Directory]::GetFiles((NG-Ext $source), '*', [System.IO.SearchOption]::AllDirectories)) {
        $sec = [System.IO.File]::GetAccessControl($f, [System.Security.AccessControl.AccessControlSections]::Owner)
        if ($sec.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -eq $script:NG_ForeignOwner) { $foreign++ }
    }
    if ($foreign -lt 2) { throw "[INVALID] 现场案卷夹里带外部所有者的文件数=$foreign，期望 >=2（冻结输入的安全属性未落地）" }

    $recInfo = New-Object System.IO.FileInfo($rec)
    if (([int]$recInfo.Attributes -band [int][System.IO.FileAttributes]::SparseFile) -eq 0) { throw '[INVALID] 现场录像在源里不是稀疏文件（冻结输入形状异常）' }
    $recAlloc = NG-AllocatedBytes $rec
    if ($recAlloc -gt $script:NG_SparseAllocatedCeiling) { throw "[INVALID] 现场录像在源里实际占用 $recAlloc 字节，超出上限（冻结输入形状异常）" }

    $compExt = NG-Ext (Join-Path $source $script:NG_CompressedRelative)
    if (-not [System.IO.File]::Exists($compExt)) { throw '[INVALID] 压缩输入文件缺失（冻结输入被破坏）' }
    if (([int](New-Object System.IO.FileInfo($compExt)).Attributes -band [int][System.IO.FileAttributes]::Compressed) -eq 0) { throw '[INVALID] 压缩输入文件在源里没有 NTFS 压缩属性（prepare 未落地运行期形状）' }

    $primExt = NG-Ext (Join-Path $source $script:NG_LinkPrimaryRelative)
    $aliasExt = NG-Ext (Join-Path $source $script:NG_LinkAliasRelative)
    if (-not [System.IO.File]::Exists($primExt) -or -not [System.IO.File]::Exists($aliasExt)) { throw '[INVALID] 硬链接输入名缺失（冻结输入被破坏）' }
    if ((NG-FileIdentity $primExt) -ne (NG-FileIdentity $aliasExt)) { throw '[INVALID] 源里两个名字并不是指向同一份数据的硬链接（prepare 未落地运行期形状）' }

    foreach ($rel in $script:NG_AuditRelatives) {
        $ae = NG-Ext (Join-Path $source $rel)
        if (-not [System.IO.File]::Exists($ae)) { throw "[INVALID] 审计输入文件缺失：$rel" }
        if (@([System.IO.File]::GetAccessControl($ae, [System.Security.AccessControl.AccessControlSections]::Audit).GetAuditRules($true, $true, [System.Security.Principal.SecurityIdentifier])).Count -lt 1) { throw "[INVALID] 源文件 $rel 上没有既有审计规则（构建期安全属性未落地）" }
    }
}

function NG-SealFieldCase() {
    $source = NG-RequireSource
    NG-RequireFieldShape
    $dest = NG-Reset $script:NG_Field
    $run = NG-RunSeal -CaseId $script:NG_Field -Source $source -Dest $dest
    if ($run.Code -ne 0) { throw "seal 退出码 $($run.Code)，期望 0；输出：$($run.Text)" }
    return [pscustomobject]@{ Source = $source; Dest = $dest; Run = $run; Map = (NG-MapOutput $run.Lines) }
}

function NG-SourceDeepRelative() {
    $srcExt = NG-Ext (Join-Path $script:NG_Cases $script:NG_Field)
    $files = [System.IO.Directory]::GetFiles($srcExt, '*', [System.IO.SearchOption]::AllDirectories)
    $deep = @($files | Where-Object { $_.Length -gt 260 })
    if ($deep.Count -lt 1) { throw '[INVALID] 现场案卷夹缺少超过 260 字符的深层文件（冻结输入被破坏）' }
    return $deep[0].Substring($srcExt.Length + 1)
}

function NG-TrueFileCount([string]$source) {
    return ([System.IO.Directory]::GetFiles((NG-Ext $source), '*', [System.IO.SearchOption]::AllDirectories)).Count
}

# ---- R2：被测产物必须复现监控台已归档的校准记录（摘要推导规则的唯一可核对基准）----
function Test-F2P_BuildReproducesCalibrationRecords {
    NG-RequireExe
    $expectedPath = Join-Path $script:NG_Calibration 'expected.json'
    if (-not (Test-Path -LiteralPath $expectedPath)) { throw '[INVALID] 校准记录缺失：C:\calibration\expected.json' }
    $records = @((Get-Content -LiteralPath $expectedPath -Raw -Encoding UTF8 | ConvertFrom-Json).records)
    if ($records.Count -ne 2) { throw "[INVALID] 校准记录应有 2 条，实际 $($records.Count)" }

    # The ordinary case uses the same public digest protocol, rather than
    # freezing the historical defective hash. Keep this check in the F2P group.
    $ordinarySource = Join-Path $script:NG_Cases 'CASE-1000'
    $ordinaryDest = NG-Reset 'CASE-1000'
    $ordinary = NG-RunSeal -CaseId 'CASE-1000' -Source $ordinarySource -Dest $ordinaryDest
    $ordinaryMap = NG-MapOutput $ordinary.Lines
    if ($ordinary.Code -ne 0 -or -not $ordinaryMap.ContainsKey('RootHash') -or
        ([string]$ordinaryMap['RootHash']) -cne (NG-RootHash $ordinarySource)) {
        throw '普通案卷 RootHash 必须符合公开的统一摘要规则'
    }

    foreach ($rec in $records) {
        $caseId = [string]$rec.caseId
        $source = Join-Path $script:NG_Calibration ('cases\' + $caseId)
        if (-not [System.IO.Directory]::Exists((NG-Ext $source))) { throw "[INVALID] 校准案卷缺失：$source" }

        $trueCount = NG-TrueFileCount $source
        if ($trueCount -ne [int]$rec.fileCount) {
            throw "[INVALID] 校准案卷 $caseId 的真实文件数=$trueCount，与归档记录 fileCount=$($rec.fileCount) 不一致（冻结输入被破坏）"
        }
        $archived = ([string]$rec.rootHash)
        $recomputed = NG-RootHash $source
        if ($recomputed -ne $archived) {
            throw "[INVALID] 校准案卷 $caseId 的归档 rootHash 与判分侧对同一份冻结输入的独立重算不一致（归档=$archived 重算=$recomputed）"
        }

        $dest = NG-Reset $caseId
        $run = NG-RunSeal -CaseId $caseId -Source $source -Dest $dest
        if ($run.Code -ne 0) {
            throw "对校准案卷 $caseId 执行 seal 退出码 $($run.Code)，期望 0；输出：$($run.Text)"
        }
        $map = NG-MapOutput $run.Lines
        if (-not $map.ContainsKey('FileCount') -or (NG-CountValue $map['FileCount']) -ne [int]$rec.fileCount) {
            throw "校准案卷 $caseId：seal 报告 FileCount=$($map['FileCount'])，监控台归档的是 $($rec.fileCount)"
        }
        if (-not $map.ContainsKey('RootHash')) { throw "校准案卷 $caseId：seal 输出未包含 RootHash 行" }
        $produced = ([string]$map['RootHash'])
        if ($produced -cne $archived) {
            throw "校准案卷 $caseId：本地产物算出 RootHash=$produced，监控台已归档并被外部审计接受过的值是 $archived；两者不一致说明这份实现遵循的摘要推导规则与采集规范不是同一修订版"
        }
    }
}

# ---- R4：现场案卷夹的封存摘要必须与判分侧独立重算逐字符一致 ----
function Test-F2P_SealRecordRootHashMatchesRecomputation {
    $ctx = NG-SealFieldCase
    if (-not [System.IO.Directory]::Exists((NG-Ext $ctx.Source))) { throw "[INVALID] 只读案卷夹在重算摘要时不可用：$($ctx.Source)" }
    if (-not $ctx.Map.ContainsKey('RootHash')) { throw 'seal 输出未包含 RootHash 行' }
    $reported = ([string]$ctx.Map['RootHash'])
    $expected = NG-RootHash $ctx.Source
    if ($reported -cne $expected) {
        throw "封存 RootHash=$reported，与判分侧对该案卷夹独立重算的 $expected 不一致"
    }
    $sub = ($env:EVIDENCE_MIRROR_REGISTRY_ROOT + '\Cases\') + $script:NG_Field
    $base64 = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')
    $k = $base64.OpenSubKey($sub)
    if ($null -eq $k) { throw "本次封存的摘要没有出现在 64 位视图的记录键里，无法核对发布值：HKLM\$sub" }
    try {
        $published = [string]$k.GetValue('RootHash', $null)
        if ($published -cne $expected) { throw "记录键里发布的 RootHash=$published，与独立重算的 $expected 不一致" }
    } finally { $k.Close() }
}

# ---- R16：镜像必须带走源文件的 Windows 安全描述符 ----
function Test-F2P_SealPreservesSecurityDescriptors {
    $ctx = NG-SealFieldCase
    $srcExt = NG-Ext $ctx.Source; $mirExt = NG-Ext $ctx.Dest
    $srcRels = NG-RelativeFiles $ctx.Source
    if ($srcRels.Count -lt $script:NG_TrueCount) { throw "[INVALID] 现场案卷夹文件数异常：$($srcRels.Count)" }

    $protectedSeen = 0
    $mismatch = @()
    foreach ($rel in $srcRels) {
        $srcPath = $srcExt + '\' + $rel
        $mirPath = $mirExt + '\' + $rel
        $srcFp = NG-SdFingerprint $srcPath
        if ($srcFp.StartsWith($script:NG_ForeignOwner + '#True#')) { $protectedSeen++ }
        if (-not [System.IO.File]::Exists($mirPath)) { $mismatch += ($rel + '（镜像里不存在）'); continue }
        $mirFp = NG-SdFingerprint $mirPath
        if ($srcFp -ne $mirFp) { $mismatch += ($rel + '（源=' + $srcFp + ' 镜像=' + $mirFp + '）') }
    }
    if ($protectedSeen -lt 2) { throw "[INVALID] 现场案卷夹里带外部所有者与受保护访问控制列表的文件数=$protectedSeen，期望 >=2" }
    if ($mismatch.Count -gt 0) {
        throw ("镜像没有把源文件的 Windows 安全描述符带过来，共 " + $mismatch.Count + " 个文件不一致： " + (($mismatch | Select-Object -First 3) -join ' ; ') + " 。所有者 SID、DACL 是否受保护、以及每一条访问控制项都必须与源文件相同")
    }
}

# ---- R17：2.2GB 现场录像必须被完整搬进镜像（含它的附加数据流）----
function Test-F2P_SealMirrorsOversizedFieldRecording {
    $ctx = NG-SealFieldCase
    $rel = $script:NG_RecordingRelative
    $srcPath = (NG-Ext $ctx.Source) + '\' + $rel
    $mirPath = (NG-Ext $ctx.Dest) + '\' + $rel
    $srcInfo = New-Object System.IO.FileInfo($srcPath)
    if ($srcInfo.Length -ne $script:NG_RecordingBytes) { throw "[INVALID] 源现场录像体积=$($srcInfo.Length)，期望 $($script:NG_RecordingBytes)" }
    if (-not [System.IO.File]::Exists($mirPath)) {
        throw "镜像里没有那个 $($script:NG_RecordingBytes) 字节的现场录像文件（$rel）：超大文件没有被收进镜像"
    }
    $mirInfo = New-Object System.IO.FileInfo($mirPath)
    if ($mirInfo.Length -ne $srcInfo.Length) {
        throw "镜像里的现场录像长度=$($mirInfo.Length)，源=$($srcInfo.Length)：超大文件被截断了"
    }
    $srcHash = NG-HashFile $srcPath
    $mirHash = NG-HashFile $mirPath
    if ($srcHash -ne $mirHash) { throw "镜像里的现场录像主数据流与源不一致（源=$srcHash 镜像=$mirHash）" }
    $srcStreams = @(NG-StreamNames $srcPath | Sort-Object)
    $mirStreams = @(NG-StreamNames $mirPath | Sort-Object)
    if (($srcStreams -join '|') -ne ($mirStreams -join '|')) {
        throw "镜像里的现场录像数据流集合与源不一致（源=[$($srcStreams -join ',')] 镜像=[$($mirStreams -join ',')]）"
    }
    foreach ($n in $srcStreams) {
        if ($n -eq ':$DATA') { continue }
        $s = NG-HashFile (NG-StreamPath $srcPath $n)
        $m = NG-HashFile (NG-StreamPath $mirPath $n)
        if ($s -ne $m) { throw "镜像里的现场录像附加数据流 $n 与源不一致" }
    }
}

# ---- R18：一次封存要么整体落地，要么什么都不留 ----
function Test-F2P_SealIsAtomicOnMidwayFailure {
    $caseId = $script:NG_Atomic
    $source = Join-Path $script:NG_Cases $caseId
    if (-not [System.IO.Directory]::Exists((NG-Ext $source))) { throw "[INVALID] 案卷夹缺失：$source" }
    NG-RequireExe
    $lockTarget = NG-Ext (Join-Path $source 'locked\inuse.bin')
    if (-not [System.IO.File]::Exists($lockTarget)) { throw "[INVALID] 冻结输入缺少 locked\inuse.bin：$source" }

    $dest = NG-Reset $caseId
    # --dest 里先放一份“上一次封存已经发布过的”镜像，内容刻意与源不同：
    # 一次失败的封存既不许把它改成半成品，也不许把它删掉或换掉。
    $destExt = NG-Ext $dest
    $priorNote = $destExt + '\intake\note.txt'
    [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($priorNote)) | Out-Null
    $noBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($priorNote, 'mirror published by an earlier seal', $noBom)
    $priorMarker = $destExt + '\from-earlier-seal.marker'
    [System.IO.File]::WriteAllText($priorMarker, 'earlier-seal-marker', $noBom)
    $priorBefore = NG-RelativeFiles $dest
    $priorNoteHash = NG-HashFile $priorNote
    if ($priorBefore.Count -ne 2) { throw '[INVALID] 无法在暂存目录里预置上一次封存的镜像' }

    # 采集端另一个进程正独占打开案卷夹里的一个文件，这次封存在中途必然读不到它。
    $lock = $null
    try {
        $lock = [System.IO.File]::Open($lockTarget, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $run = NG-RunSeal -CaseId $caseId -Source $source -Dest $dest
    } finally {
        if ($null -ne $lock) { $lock.Close(); $lock = $null }
    }

    if ($run.Code -eq 0) {
        throw "案卷夹里有文件正被别的进程独占打开，seal 仍以退出码 0 报告成功；输出：$($run.Text)"
    }
    if (-not [System.IO.File]::Exists($priorMarker)) { throw "封存中途失败后，$dest 里上一次封存留下的内容被删掉了；失败的封存不许动 --dest 原有的东西" }
    if (-not [System.IO.File]::Exists($priorNote)) { throw "封存中途失败后，$dest\intake\note.txt 不见了；失败的封存不许动 --dest 原有的东西" }
    if ((NG-HashFile $priorNote) -ne $priorNoteHash) { throw "封存中途失败后，$dest\intake\note.txt 的内容被改写了：--dest 里留下的是半成品镜像" }
    $priorAfter = NG-RelativeFiles $dest
    if (($priorAfter -join '|') -ne ($priorBefore -join '|')) {
        throw "封存中途失败后 --dest 的文件集合变了：失败前=[$($priorBefore -join ', ')] 失败后=[$($priorAfter -join ', ')]"
    }
    if ([System.IO.Directory]::Exists((NG-Ext $script:NG_Stage))) {
        $leftovers = @([System.IO.Directory]::GetFileSystemEntries((NG-Ext $script:NG_Stage)) | Where-Object { ([System.IO.Path]::GetFileName($_)).StartsWith($caseId, [System.StringComparison]::Ordinal) -and ([System.IO.Path]::GetFileName($_)) -cne $caseId })
        if ($leftovers.Count -gt 0) {
            throw ("失败的封存在暂存区里留下了本次创建的中间目录： " + (($leftovers | ForEach-Object { [System.IO.Path]::GetFileName($_) }) -join ', '))
        }
    }
    $sub = ($env:EVIDENCE_MIRROR_REGISTRY_ROOT + '\Cases\') + $caseId
    foreach ($view in @('Registry64', 'Registry32')) {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', $view)
        $k = $base.OpenSubKey($sub)
        if ($null -ne $k) { $k.Close(); throw "封存中途失败，但 $view 视图里出现了 $caseId 的封存记录（HKLM\$sub）；失败的封存不得发布记录" }
    }
}

# ---- R19：取证镜像的 MACE 时间属于证据本身 ----
function Test-F2P_SealPreservesFileTimes {
    $ctx = NG-SealFieldCase
    $srcExt = NG-Ext $ctx.Source; $mirExt = NG-Ext $ctx.Dest
    $srcRels = NG-RelativeFiles $ctx.Source
    $frozen = 0
    $bad = @()
    foreach ($rel in $srcRels) {
        $srcInfo = New-Object System.IO.FileInfo($srcExt + '\' + $rel)
        if ($srcInfo.CreationTimeUtc.Year -ne 2024) { throw "[INVALID] 源文件 $rel 的创建时间不是冻结字面量（$($srcInfo.CreationTimeUtc.ToString('o'))），冻结输入被破坏" }
        $frozen++
        $mirPath = $mirExt + '\' + $rel
        if (-not [System.IO.File]::Exists($mirPath)) { $bad += ($rel + '（镜像里不存在）'); continue }
        $mirInfo = New-Object System.IO.FileInfo($mirPath)
        if ($mirInfo.CreationTimeUtc -ne $srcInfo.CreationTimeUtc) {
            $bad += ($rel + '（创建时间 源=' + $srcInfo.CreationTimeUtc.ToString('o') + ' 镜像=' + $mirInfo.CreationTimeUtc.ToString('o') + '）')
        }
        if ($mirInfo.LastWriteTimeUtc -ne $srcInfo.LastWriteTimeUtc) {
            $bad += ($rel + '（最后写入时间 源=' + $srcInfo.LastWriteTimeUtc.ToString('o') + ' 镜像=' + $mirInfo.LastWriteTimeUtc.ToString('o') + '）')
        }
    }
    if ($frozen -lt $script:NG_TrueCount) { throw "[INVALID] 现场案卷夹文件数=$frozen，期望 $($script:NG_TrueCount)" }
    if ($bad.Count -gt 0) {
        throw ("镜像里的文件时间与源不一致，共 " + $bad.Count + " 处： " + (($bad | Select-Object -First 3) -join ' ; ') + " 。创建时间与最后写入时间（UTC）都必须与源文件逐位相同")
    }
}

# ---- R2：超过 260 字符的深层文件必须进镜像 ----
function Test-F2P_SealReachesBeyondMaxPath {
    $ctx = NG-SealFieldCase
    $deepRel = NG-SourceDeepRelative
    $mirrorDeep = (NG-Ext $ctx.Dest) + '\' + $deepRel
    $sourceDeep = (NG-Ext $ctx.Source) + '\' + $deepRel
    if (-not [System.IO.File]::Exists($mirrorDeep)) {
        throw "镜像未收录超过 260 字符的深层文件（相对路径 $deepRel）；深层目录链在经典路径上限处被静默截断"
    }
    if ((NG-HashFile $mirrorDeep) -ne (NG-HashFile $sourceDeep)) { throw '深层文件已进入镜像但主数据流内容与源不一致' }
}

# ---- R3：seal 报告的 FileCount 必须是案卷夹的真实文件数 ----
function Test-F2P_SealReportsTrueFileCount {
    $ctx = NG-SealFieldCase
    $trueCount = NG-TrueFileCount $ctx.Source
    if (-not $ctx.Map.ContainsKey('FileCount')) { throw 'seal 输出未包含 FileCount 行' }
    $reported = NG-CountValue $ctx.Map['FileCount']
    if ($reported -ne $trueCount) { throw "seal 报告 FileCount=$reported，但案卷夹真实文件数=$trueCount（漏收文件却仍报成功）" }
}

# ---- R1：镜像的文件集合与逐文件主数据流内容必须与案卷夹完全一致 ----
function Test-F2P_SealMirrorIsLossless {
    $ctx = NG-SealFieldCase
    if (-not [System.IO.Directory]::Exists((NG-Ext $ctx.Source))) { throw "[INVALID] 只读案卷夹在核对过程中消失：$($ctx.Source)" }
    if (-not [System.IO.Directory]::Exists((NG-Ext $ctx.Dest))) { throw "封存输出目录不存在，候选没有生成要求的镜像：$($ctx.Dest)" }
    $srcRels = NG-RelativeFiles $ctx.Source
    $mirRels = NG-RelativeFiles $ctx.Dest
    $missing = @($srcRels | Where-Object { $mirRels -notcontains $_ })
    $extra   = @($mirRels | Where-Object { $srcRels -notcontains $_ })
    if ($missing.Count -gt 0 -or $extra.Count -gt 0) {
        throw "镜像与案卷夹文件集合不一致：缺失 [$($missing -join ', ')] 多余 [$($extra -join ', ')]"
    }
    $srcExt = NG-Ext $ctx.Source; $mirExt = NG-Ext $ctx.Dest
    foreach ($rel in $srcRels) {
        if ((NG-HashFile ($srcExt + '\' + $rel)) -ne (NG-HashFile ($mirExt + '\' + $rel))) { throw "镜像文件内容与源不一致：$rel" }
    }
}

# ---- R6：附加数据流必须原样带进镜像（短路径上的那些）----
function Test-F2P_SealPreservesAlternateDataStreams {
    $ctx = NG-SealFieldCase
    $srcExt = NG-Ext $ctx.Source; $mirExt = NG-Ext $ctx.Dest
    $archiveRel = 'names\archive.dat'
    $srcArchive = $srcExt + '\' + $archiveRel
    if (-not [System.IO.File]::Exists($srcArchive)) { throw "[INVALID] 冻结输入缺少 $archiveRel" }
    $srcStreams = @(NG-StreamNames $srcArchive | Sort-Object)
    if ($srcStreams -notcontains 'Northgate.Chain:$DATA') { throw "[INVALID] $archiveRel 上没有 Northgate.Chain 附加数据流（冻结输入被破坏）" }
    $mirArchive = $mirExt + '\' + $archiveRel
    if (-not [System.IO.File]::Exists($mirArchive)) { throw "镜像里缺少 $archiveRel" }
    $mirStreams = @(NG-StreamNames $mirArchive | Sort-Object)
    if (($srcStreams -join '|') -ne ($mirStreams -join '|')) {
        throw "镜像里 $archiveRel 的数据流集合与源不一致（源=[$($srcStreams -join ',')] 镜像=[$($mirStreams -join ',')]）；只搬主数据流不算忠实副本"
    }
    $mismatch = @()
    foreach ($rel in (NG-RelativeFiles $ctx.Source)) {
        $s = $srcExt + '\' + $rel; $m = $mirExt + '\' + $rel
        if (-not [System.IO.File]::Exists($m)) { continue }
        $ss = @(NG-StreamNames $s | Sort-Object); $ms = @(NG-StreamNames $m | Sort-Object)
        if (($ss -join '|') -ne ($ms -join '|')) { $mismatch += ($rel + '（源 ' + $ss.Count + ' 个流 / 镜像 ' + $ms.Count + ' 个流）') }
    }
    if ($mismatch.Count -gt 0) { throw ("镜像里有 " + $mismatch.Count + " 个文件的数据流集合与源不一致： " + ($mismatch -join ' ; ')) }
}

# ---- R12：超长路径上的附加数据流同样要保全 ----
function Test-F2P_SealPreservesAdsOnDeepLongPathFile {
    $ctx = NG-SealFieldCase
    $deepRel = NG-SourceDeepRelative
    $srcDeep = (NG-Ext $ctx.Source) + '\' + $deepRel
    $mirDeep = (NG-Ext $ctx.Dest) + '\' + $deepRel
    $srcStreams = @(NG-StreamNames $srcDeep)
    if ($srcStreams -notcontains 'Northgate.Chain:$DATA') { throw '[INVALID] 深层文件上没有 Northgate.Chain 附加数据流（冻结输入被破坏）' }
    if (-not [System.IO.File]::Exists($mirDeep)) { throw "镜像里没有那个超过 260 字符的深层文件，谈不上保全它的附加数据流" }
    $mirStreams = @(NG-StreamNames $mirDeep)
    if ($mirStreams -notcontains 'Northgate.Chain:$DATA') {
        throw "镜像里的深层文件丢失了附加数据流 Northgate.Chain（源=[$($srcStreams -join ',')] 镜像=[$($mirStreams -join ',')]）：附加数据流处理在超过经典路径上限的文件上不成立"
    }
    $srcChain = NG-HashFile (NG-StreamPath $srcDeep 'Northgate.Chain:$DATA')
    $mirChain = NG-HashFile (NG-StreamPath $mirDeep 'Northgate.Chain:$DATA')
    if ($srcChain -ne $mirChain) { throw '深层文件的附加数据流 Northgate.Chain 内容与源不一致' }
}

# ---- R5：记录必须发布在 64 位监控台真正读取的原生视图里，且每次封存都重建 ----
function Test-F2P_SealRecordVisibleInNative64BitView {
    $source = NG-RequireSource
    NG-RequireFieldShape
    $dest = NG-Reset $script:NG_Field
    $sub = ($env:EVIDENCE_MIRROR_REGISTRY_ROOT + '\Cases\') + $script:NG_Field
    $base64 = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')
    # 先按“历史遗留”的样子在同一个键上预置一个契约之外的值，再执行本次封存，
    # 用来检验发布逻辑是不是真的重建了记录，而不是往旧键上叠加。
    $seed = $base64.CreateSubKey($sub)
    if ($null -eq $seed) { throw '[INVALID] 无法在 64 位视图里预置历史遗留的封存记录值' }
    $seed.SetValue('LegacyDigest', 'stale-value-left-by-an-earlier-build', [Microsoft.Win32.RegistryValueKind]::String)
    $seed.Close()

    $run = NG-RunSeal -CaseId $script:NG_Field -Source $source -Dest $dest
    if ($run.Code -ne 0) { throw "seal 退出码 $($run.Code)，期望 0；输出：$($run.Text)" }
    $map = NG-MapOutput $run.Lines

    $k = $base64.OpenSubKey($sub)
    if ($null -eq $k) { throw "64 位监控台读取的原生 64 位注册表视图里没有本案封存记录（HKLM\$sub）；记录被写进了别的视图" }
    try {
        foreach ($vn in @('FileCount', 'RootHash', 'MirrorRoot', 'CompletedUtc')) {
            if ($null -eq $k.GetValue($vn, $null)) { throw "64 位视图的封存记录缺少 $vn 值（本案记录被发布到了别的位置）" }
        }
        $names = @($k.GetValueNames())
        if ($names -contains 'LegacyDigest') { throw '封存记录里残留了本次封存之前就存在的值 LegacyDigest；每次封存都必须重建这份记录，而不是往旧键上叠加' }
        $unexpected = @($names | Where-Object { @('FileCount', 'RootHash', 'MirrorRoot', 'CompletedUtc') -notcontains $_ })
        if ($unexpected.Count -gt 0) { throw "封存记录键里存在契约表格之外的值：$($unexpected -join ', ')" }
        if ($k.GetValueKind('FileCount') -ne [Microsoft.Win32.RegistryValueKind]::DWord) { throw "FileCount 的值类型是 $($k.GetValueKind('FileCount'))，契约要求 REG_DWORD" }
        foreach ($vn in @('RootHash', 'MirrorRoot', 'CompletedUtc')) {
            if ($k.GetValueKind($vn) -ne [Microsoft.Win32.RegistryValueKind]::String) { throw "$vn 的值类型是 $($k.GetValueKind($vn))，契约要求 REG_SZ" }
        }
        $trueCount = NG-TrueFileCount $source
        if ([int]$k.GetValue('FileCount') -ne $trueCount) { throw "记录里的 FileCount=$($k.GetValue('FileCount'))，案卷夹真实文件数=$trueCount" }
        if (([string]$k.GetValue('MirrorRoot')) -cne $dest) { throw "记录里的 MirrorRoot='$($k.GetValue('MirrorRoot'))'，与调用方传入的 --dest '$dest' 不逐字符相同" }
        if (-not $map.ContainsKey('MirrorRoot') -or ([string]$map['MirrorRoot']) -cne $dest) { throw "seal 输出的 MirrorRoot='$($map['MirrorRoot'])'，与 --dest '$dest' 不逐字符相同（被改写或规范化了）" }
    } finally { $k.Close() }

    $q = NG-RunNative -FilePath 'reg.exe' -Arguments @('query', ('HKLM\' + $sub), '/reg:64')
    if ($q.Code -ne 0) { throw "64 位 reg.exe /reg:64 查不到本案封存记录：$($q.Text)" }
    if ($q.Text -notmatch 'RootHash') { throw "64 位 reg.exe 查到的记录里没有 RootHash 值：$($q.Text)" }
}

# ---- R13：同一案卷只允许一份权威记录 ----
function Test-F2P_SealRecordAbsentFromRedirected32BitView {
    $ctx = NG-SealFieldCase
    $sub = ($env:EVIDENCE_MIRROR_REGISTRY_ROOT + '\Cases\') + $script:NG_Field
    $base32 = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry32')
    $k = $base32.OpenSubKey($sub)
    if ($null -ne $k) {
        $k.Close()
        throw "32 位重定向视图里也出现了本案的封存记录（HKLM\SOFTWARE\WOW6432Node\EvidenceMirror\Cases\$($script:NG_Field)）；同一案卷只允许一份权威记录，多写一份会让监控台与组件本地读到两个可能不一致的版本"
    }
    $q = NG-RunNative -FilePath 'reg.exe' -Arguments @('query', ('HKLM\' + $sub), '/reg:32')
    if ($q.Code -eq 0) { throw "32 位 reg.exe 仍能查到本案封存记录：$($q.Text)" }
    if ($ctx.Map.Count -lt 1) { throw 'seal 未产生任何输出行' }
}

# ---- R14：report 必须把刚发布的那份记录原样读回来 ----
function Test-F2P_ReportReadsBackSealRecord {
    $ctx = NG-SealFieldCase
    $rep = NG-RunNative -FilePath $script:NG_EXE -Arguments @('report', '--case', $script:NG_Field)
    if ($rep.Code -ne 0) { throw "report --case $($script:NG_Field) 退出码 $($rep.Code)，期望 0；输出：$($rep.Text)（发布记录的位置与读回记录的位置不是同一个）" }
    $map = NG-MapOutput $rep.Lines
    foreach ($key in @('CaseId', 'FileCount', 'RootHash', 'MirrorRoot', 'CompletedUtc')) {
        if (-not $map.ContainsKey($key)) { throw "report 输出缺少 $key 行" }
    }
    $trueCount = NG-TrueFileCount $ctx.Source
    if ((NG-CountValue $map['FileCount']) -ne $trueCount) { throw "report 读回 FileCount=$($map['FileCount'])，期望 $trueCount" }
    if (([string]$map['RootHash']) -cne ([string]$ctx.Map['RootHash'])) { throw "report 读回 RootHash=$($map['RootHash'])，与本次 seal 发布的 $($ctx.Map['RootHash']) 不一致" }
    if ([string]$map['MirrorRoot'] -cne $ctx.Dest) { throw "report 读回 MirrorRoot='$($map['MirrorRoot'])'，与本次封存的 --dest '$($ctx.Dest)' 不一致" }
    $timestamp = [string]$map['CompletedUtc']
    $parsed = [DateTimeOffset]::MinValue
    $inv = [System.Globalization.CultureInfo]::InvariantCulture
    $isoUtc = $timestamp -cmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)$'
    $parseable = [DateTimeOffset]::TryParse($timestamp, $inv, [System.Globalization.DateTimeStyles]::None, [ref]$parsed)
    if (-not $isoUtc -or -not $parseable -or $parsed.Offset -ne [TimeSpan]::Zero) {
        throw "report CompletedUtc='$timestamp' must be an ISO 8601 UTC timestamp"
    }
}

# ---- R15：镜像恰好等于案卷夹，且重复封存结果一致 ----
function Test-F2P_SealPurgesStaleEntriesAndIsIdempotent {
    $source = NG-RequireSource
    NG-RequireFieldShape
    $dest = NG-Reset $script:NG_Field
    $ghostRel = 'names\stale-from-previous-run.txt'
    $ghost = (NG-Ext $dest) + '\' + $ghostRel
    [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($ghost)) | Out-Null
    [System.IO.File]::WriteAllText($ghost, 'leftover from an earlier seal', (New-Object System.Text.UTF8Encoding($false)))
    if (-not [System.IO.File]::Exists($ghost)) { throw '[INVALID] 无法在暂存目录里预置历史遗留文件' }

    $first = NG-RunSeal -CaseId $script:NG_Field -Source $source -Dest $dest
    if ($first.Code -ne 0) { throw "seal 退出码 $($first.Code)，期望 0；输出：$($first.Text)" }
    $srcRels = NG-RelativeFiles $source
    $mirRels = NG-RelativeFiles $dest
    $extra   = @($mirRels | Where-Object { $srcRels -notcontains $_ })
    $missing = @($srcRels | Where-Object { $mirRels -notcontains $_ })
    if ($extra.Count -gt 0 -or $missing.Count -gt 0) {
        throw "镜像不是案卷夹的精确副本：多余 [$($extra -join ', ')] 缺失 [$($missing -join ', ')]；--dest 里上一次封存遗留的条目必须在本次封存后消失"
    }

    $second = NG-RunSeal -CaseId $script:NG_Field -Source $source -Dest $dest
    if ($second.Code -ne 0) { throw "重复 seal 退出码 $($second.Code)，期望 0；输出：$($second.Text)" }
    $mapA = NG-MapOutput $first.Lines
    $mapB = NG-MapOutput $second.Lines
    if ((NG-CountValue $mapA['FileCount']) -ne (NG-CountValue $mapB['FileCount'])) { throw "重复封存 FileCount 不一致：$($mapA['FileCount']) vs $($mapB['FileCount'])" }
    if (([string]$mapA['RootHash']) -ne ([string]$mapB['RootHash'])) { throw "重复封存 RootHash 不一致：$($mapA['RootHash']) vs $($mapB['RootHash'])" }
    $mirRels2 = NG-RelativeFiles $dest
    if (($mirRels2 -join '|') -ne ($srcRels -join '|')) { throw '重复封存后镜像文件集合与案卷夹仍不一致' }
    $stale = (NG-Ext $dest) + '\' + $ghostRel
    if ([System.IO.File]::Exists($stale)) { throw "重复封存后 --dest 里仍残留案卷夹中并不存在的 $ghostRel" }
}
# ---- R21：镜像必须带走源文件的审计规则（SACL）----
function Test-F2P_SealPreservesAuditRules {
    $ctx = NG-SealFieldCase
    $srcExt = NG-Ext $ctx.Source; $mirExt = NG-Ext $ctx.Dest
    foreach ($rel in $script:NG_AuditRelatives) {
        $s = $srcExt + '\' + $rel
        $m = $mirExt + '\' + $rel
        if (-not [System.IO.File]::Exists($m)) { throw "镜像里缺少带审计规则的文件：$rel" }
        $want = NG-SaclFingerprint $s
        $got = NG-SaclFingerprint $m
        if ($got -ne $want) { throw "镜像里 $rel 的审计规则与源不一致：源=[$want] 镜像=[$got]" }
    }
}

# ---- R22：镜像必须保住现场录像的稀疏形状（逻辑体积照搬，但不按逻辑体积占盘）----
function Test-F2P_MirrorKeepsFieldRecordingSparse {
    $ctx = NG-SealFieldCase
    $src = (NG-Ext $ctx.Source) + '\' + $script:NG_RecordingRelative
    $mir = (NG-Ext $ctx.Dest) + '\' + $script:NG_RecordingRelative
    if (-not [System.IO.File]::Exists($src)) { throw '[INVALID] 现场录像在源里缺失（冻结输入被破坏）' }
    if (-not [System.IO.File]::Exists($mir)) { throw "镜像里缺少现场录像：$($script:NG_RecordingRelative)" }
    $srcInfo = New-Object System.IO.FileInfo($src)
    $mirInfo = New-Object System.IO.FileInfo($mir)
    if ($mirInfo.Length -ne $srcInfo.Length) { throw "镜像里现场录像的逻辑体积=$($mirInfo.Length)，源是 $($srcInfo.Length)" }
    if (([int]$mirInfo.Attributes -band [int][System.IO.FileAttributes]::SparseFile) -eq 0) {
        throw "镜像里的现场录像不是稀疏文件（属性=$($mirInfo.Attributes)）：源里它是稀疏的，忠实副本必须保住这个形状"
    }
    $srcAlloc = NG-AllocatedBytes $src
    $mirAlloc = NG-AllocatedBytes $mir
    if ($mirAlloc -gt $script:NG_SparseAllocatedCeiling) {
        throw ("镜像里的现场录像实际占用 {0} 字节（逻辑体积 {1} 字节，源里只占 {2} 字节）：稀疏区间被当成真实数据落了盘" -f $mirAlloc, $mirInfo.Length, $srcAlloc)
    }
    if ((NG-HashFile $mir) -ne (NG-HashFile $src)) { throw '镜像里现场录像的字节与源不一致' }
}

# ---- R23：镜像必须保住 NTFS 压缩形状 ----
function Test-F2P_MirrorKeepsCompressedFileCompressed {
    $ctx = NG-SealFieldCase
    $rel = $script:NG_CompressedRelative
    $src = (NG-Ext $ctx.Source) + '\' + $rel
    $mir = (NG-Ext $ctx.Dest) + '\' + $rel
    if (-not [System.IO.File]::Exists($src)) { throw '[INVALID] 压缩输入文件在源里缺失（冻结输入被破坏）' }
    if (-not [System.IO.File]::Exists($mir)) { throw "镜像里缺少文件：$rel" }
    $srcInfo = New-Object System.IO.FileInfo($src)
    $mirInfo = New-Object System.IO.FileInfo($mir)
    if (([int]$srcInfo.Attributes -band [int][System.IO.FileAttributes]::Compressed) -eq 0) { throw '[INVALID] 源里的压缩输入文件没有压缩属性（prepare 未落地运行期形状）' }
    if ($mirInfo.Length -ne $srcInfo.Length) { throw "镜像里 $rel 的逻辑体积=$($mirInfo.Length)，源是 $($srcInfo.Length)" }
    if (([int]$mirInfo.Attributes -band [int][System.IO.FileAttributes]::Compressed) -eq 0) {
        throw "镜像里 $rel 不再是 NTFS 压缩文件（属性=$($mirInfo.Attributes)）：源里它是压缩存放的，忠实副本必须保住这个形状"
    }
    $mirAlloc = NG-AllocatedBytes $mir
    # Windows lazy-writer can publish the compressed allocation after the
    # collector exits: observed 234000 -> 32768 bytes after ~6s with identical
    # data and attributes. Poll the original predicate, without flushing,
    # rewriting or compressing the candidate output. The threshold is unchanged.
    $allocationWait = [Diagnostics.Stopwatch]::StartNew()
    while (($mirAlloc * 4) -gt $mirInfo.Length -and $allocationWait.Elapsed.TotalSeconds -lt 60) {
        Start-Sleep -Seconds 1
        $mirAlloc = NG-AllocatedBytes $mir
    }
    $allocationWait.Stop()
    Write-Host ('[allocation-observation] seconds={0:F1} bytes={1} length={2}' -f $allocationWait.Elapsed.TotalSeconds, $mirAlloc, $mirInfo.Length)
    if (($mirAlloc * 4) -gt $mirInfo.Length) {
        throw ("镜像里 $rel 只带了压缩属性却没有真的压缩存放：实际占用 {0} 字节，逻辑体积 {1} 字节" -f $mirAlloc, $mirInfo.Length)
    }
    if ((NG-HashFile $mir) -ne (NG-HashFile $src)) { throw "镜像里 $rel 的字节与源不一致" }
}

# ---- R24：源里指向同一份数据的多个名字，在镜像里必须仍然指向同一份数据 ----
function Test-F2P_MirrorPreservesHardLinkIdentity {
    $ctx = NG-SealFieldCase
    $primRel = $script:NG_LinkPrimaryRelative; $aliasRel = $script:NG_LinkAliasRelative
    $srcPrim = (NG-Ext $ctx.Source) + '\' + $primRel
    $srcAlias = (NG-Ext $ctx.Source) + '\' + $aliasRel
    $mirPrim = (NG-Ext $ctx.Dest) + '\' + $primRel
    $mirAlias = (NG-Ext $ctx.Dest) + '\' + $aliasRel
    if (-not [System.IO.File]::Exists($srcPrim) -or -not [System.IO.File]::Exists($srcAlias)) { throw '[INVALID] 源里的硬链接名缺失（冻结输入被破坏）' }
    $srcId = NG-FileIdentity $srcPrim
    if ($srcId -ne (NG-FileIdentity $srcAlias)) { throw "[INVALID] 源里 $primRel 与 $aliasRel 不是同一份数据的两个名字（冻结输入形状异常）" }
    if (-not [System.IO.File]::Exists($mirPrim)) { throw "镜像里缺少名字：$primRel" }
    if (-not [System.IO.File]::Exists($mirAlias)) { throw "镜像里缺少名字：$aliasRel" }
    $mirPrimId = NG-FileIdentity $mirPrim
    $mirAliasId = NG-FileIdentity $mirAlias
    if ($mirPrimId -ne $mirAliasId) {
        throw ("镜像里 $primRel 与 $aliasRel 变成了两份互不相干的数据（标识 $mirPrimId 与 $mirAliasId）：源里它们是同一份数据的两个名字，忠实副本必须保住这个身份")
    }
    $mirLinks = [int]($mirPrimId.Split(':')[2])
    $srcLinks = [int]($srcId.Split(':')[2])
    if ($mirLinks -ne $srcLinks) { throw "镜像里这份数据的名字数=$mirLinks，源里是 $srcLinks" }
    if ((NG-HashFile $mirPrim) -ne (NG-HashFile $srcPrim)) { throw "镜像里 $primRel 的字节与源不一致" }
}
