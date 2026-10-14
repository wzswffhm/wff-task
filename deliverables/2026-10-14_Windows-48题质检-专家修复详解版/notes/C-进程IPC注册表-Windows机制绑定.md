# C · 进程 / IPC / 注册表类 Windows 机制绑定逆向分析

> 分析对象（8 题）：`002.1` windows-d4-litemonitor-001、`002.2` windows-d6-0007、
> `002.6` windows-powershell-ads-001、`003` windows-file-share-classification-002、
> `018` windows-named-event-003、`020` windows-named-mutex-002、
> `040` windows-subprocess-reader-error-005、`043` windows-hkcu-env-expand-001。
>
> 全部证据来自只读检视（未修改 `extracted/` 内任何文件）。下文路径中
> `E = deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted`。
> 每条证据都给 `文件:行号` 与代码摘录；行号对应当前文件实际内容。

---

## 总结论

我方被质检判定不满足 Windows 题要求的三道题（wchunk-216 / wfmt-215 / wlogseg-218）的共性是：
判据建立在**平台无关的字节层**（容器格式、CRC、流式 IO），任何 POSIX 主机上都能用纯字节复现，
Windows 只是"恰好运行环境"，不是**判据的一部分**。

这 8 道被评"Windows 价值高"的题走的是另一条路，可以概括为**三层锁定**：

1. **题面层锁定**：题面直接点名 Windows 专属对象或机制，并把验收点写成"只有该机制才产生的可观测差异"。
   例如 `RegistryNotify` / `RegNotifyChangeKeyValue` 的值变更语义（002.1）、
   `EVIDENCE_MIRROR_REGISTRY_ROOT` + 原生 64 位注册表视图 + DACL/SACL/ADS/硬链接（002.2）、
   NTFS `Zone.Identifier` ADS + 同文件对象身份（002.6）、
   Win32 共享打开模式与原始 `win32` 错误码 32/33（003）、
   命名 Event（018）、命名 Mutex 的 abandoned 语义（020）、
   Windows 线程式 subprocess 管道读取器（040）、
   `REG_EXPAND_SZ` 与未展开原文（043）。
   **没有任何一题出现"不需要其他操作系统版本"这类免责句**；相反，8 题全部把 OS/edition/build/shell/
   filesystem 冻结到具体值，并在偏离时直接失败（详见各题环境层）。

2. **环境层锁定**：`validate_environment.ps1`（或 Dockerfile 构建期）不只检查"是不是 Windows"，
   而是**当场创建/读写真实机制对象**作为探针；探针不成立即抛错，判分侧把这种情况记为 `INVALID`
   而不是"模型失败"。典型：002.1 在 HKCU 64 位视图写 `REG_SZ/REG_QWORD/REG_EXPAND_SZ` 再读回；
   002.6 真造一个 `Zone.Identifier` ADS，读不到就报 `NTFS alternate data streams are unavailable.`；
   043 先验证注册表能否原生 roundtrip kind/raw；003/002.2 以 NTFS 卷格式、build 20348、
   Framework 编译器、管理员令牌为硬门槛。

3. **验证层锁定**：评测器**自己**成为一个独立的 Windows 对象持有者，再观测候选是否操作了同一个内核对象。
   这是这批题最值得抄的一点：判据不读候选源码、不比对字符串近似，而是
   - 让**第二个进程**持有同名 Event/Mutex 的句柄，看候选能不能把同一个内核对象置位（018:21、020:11）；
   - 让**第二个进程**以真实凭据 + Job Object 运行候选，并用 `LockFileEx` 真加字节范围锁（003）；
   - 用 `CreateFileW` 的 share mode 真持有流句柄，使候选的删除操作必然拿到共享冲突（002.6）；
   - 用 `GetFileInformationByHandle` 的 `VolumeSerialNumber + FileIndex` 作为"文件身份"，让"路径字符串判等"
     的实现当场暴露（002.6、002.2）；
   - 用 `GetValueKind` + `DoNotExpandEnvironmentNames` 判定注册表类型与未展开原文（043、002.2）；
   - 用 `Process.TotalProcessorTime` 的空闲增量把"轮询冒充事件"一票否决（002.1:590-615）；
   - 用 `threading.excepthook` 钩子 + 线程残留检测把"异常只留在 reader 线程里"的结构性错误变成判据（040）。

**方法论对照**：我方题目的"正确性"可由字节序列唯一确定；这批题目的"正确性"必须由
**某个只有 Windows 内核提供的对象的状态**来确定（键的值类型与 last-write 时间戳、内核事件/互斥体状态、
文件对象的身份与共享模式、SACL 审计规则、管道读取线程的异常归属）。
一旦判据必须经过这些对象，实现就无法在非 Windows 上"绕开机制、只对答案"。

### 8 题机制锚点与判据形态速览

| 样本 | 题包 id | 机制锚点（题面点名） | 环境层"非 Windows 必失败"保障 | 验证层"必须真用机制"的关键判据 |
|---|---|---|---|---|
| 002.1 | windows-d4-litemonitor-001 | `RegNotifyChangeKeyValue` 值变更通知、`DateTimeKind.Utc`、空闲 CPU 上限、键删除重建自愈 | `os_is_windows` + `os_architecture_x64` + HKCU 64 位视图读写探针 | 空闲 5s CPU < 40ms（前后各写一次证明活着）；同值换 registry kind 仍须回调；删键/整树 Purge 后 5-6s 内仍须回调 |
| 002.2 | windows-d6-0007 | HKLM 原生 64 位视图、DACL/SACL 继承状态、ADS/硬链接/稀疏/压缩、x86 产物、崩溃恢复 | 64 位 OS + Framework csc + `DriveFormat -eq 'NTFS'` + 管理员令牌 + 16 文件夹具 | ACE 二进制指纹 + 继承位分组；`reg.exe /reg:64` 与 32 位视图"必须没有"；checkpoint 握手后 `Kill()` 再 recover |
| 002.6 | windows-powershell-ads-001 | `Zone.Identifier` ADS、同一文件对象身份、PS 5.1/7 双宿主、Atomic 回滚 | `$env:OS -ne 'Windows_NT'` + 真造 ADS 探针 | `GetFileInformationByHandle` 身份不变；WhatIf 零副作用；独占 ADS 句柄制造提交中途失败后逐文件核对还原 |
| 003 | windows-file-share-classification-002 | Win32 `FileShare`、`ERROR_SHARING_VIOLATION(32)`/`33`、`LockFileEx`、低权账户 | build 20348 + x64 + Framework64 csc；隔离本地用户 + 防火墙 + 双视图注册表 ACL | 评测器用 `CreateFileW(share=7)` 真持句柄，断言候选返回 `('SharingViolation',32)`；`LockFileEx` 重叠返回 `('LockViolation',33)` |
| 018 | windows-named-event-003 | 命名 Event（ManualReset）、句柄生命周期、跨进程 | 非 Windows 或 PS ≠ 7.5.10 即 `throw 'Frozen Windows PowerShell runtime required'` | 测试进程自建同名 `EventWaitHandle` 并 `WaitOne(0)`；`Start-Process pwsh.exe` 子进程 Signal 后父进程观测 |
| 020 | windows-named-mutex-002 | 命名 Mutex、abandoned 状态、跨进程互斥 | `!$IsWindows` → `throw 'Windows required'`；build 20348 精确匹配 | 子进程 `[Environment]::Exit(0)` 造 abandoned mutex；测试进程用同名 `Mutex` 互认；`Stopwatch` 量测真实持有时长 |
| 040 | windows-subprocess-reader-error-005 | Windows 线程式 reader + 匿名管道、异常五元组、完成顺序 | `$env:OS -ne 'Windows_NT'`/非 AMD64 即 throw；Python 侧断言 `os.name=="nt"` | reader 完成顺序决定抛哪个异常（镜像双向用例）；`threading.excepthook` 无未处理异常 + 无线程残留 |
| 043 | windows-hkcu-env-expand-001 | `REG_EXPAND_SZ`/`REG_SZ` + `DoNotExpandEnvironmentNames`、值名大小写去重 | 非 Windows/PS<7.5/build≠20348 即 throw；注册表 kind/raw roundtrip 探针 | 逐项比对注册表原生 Kind 与未展开 Raw（顺序一致）；全键树快照前后逐字符相等 |

---

## 002.1 windows-d4-litemonitor-001：注册表原生变更通知取代轮询

### 题面层

题面把"要不要用 Windows 机制"直接写成任务目标：把定时轮询改造成**注册表原生变更通知**，
并点名两个待实现方法。

> **原文**（[instruction.md:22-25](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/instruction.md#L22-L25>)）
> ```
> 1. 实现 `RegistryNotify` 的两个公开方法：对状态镜像注册表键的**值变更**做事件驱动的订阅通知，
>    以及读取该键的最后写入时间（以 UTC 表示）。
> 2. 把 `StatusMirror.StartRefresher` 从「定时轮询比较代号」改造成基于上述订阅的事件驱动实现，
>    并清掉不再需要的遗留轮询代码。
> ```
> **解释**：验收锚定在两个只有 Windows 注册表才有的能力上——"值变更通知"和"键的最后写入时间"。
> 这不是"读文件算哈希"，而是必须调用 `RegNotifyChangeKeyValue` / 读取键元数据。

> **原文**（[instruction.md:30-35](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/instruction.md#L30-L35>)）
> ```
> 可观测验收要求：时延上限、空闲时的 CPU 开销上限、通知的触发范围与过滤语义、连续变更与密集突发写入下的
> 自动重新挂接、多个订阅共存与退订语义、回调自身抛异常时的行为、目标键被删除重建（含整棵镜像树被彻底清理后
> 重新发布）时的自愈、最后写入时间的时间刻度与 `DateTimeKind`、键缺失时的返回值与「不得代为创建」、
> 以及任何情况下都不得抛异常。
>
> 这些约定会被一个独立评测器在真实 Windows 上逐条执行验证（跨进程写注册表、删除并重建键、量测空闲 CPU、
> 强制结束进程等等）。**文档没有写明的行为一律不作要求。**
> ```
> **解释**：一句话交代了全部判据维度，并明确评测器会在真实 Windows 上做**跨进程写注册表、删键重建、
> 量测空闲 CPU、强制结束进程**——这四件事全是 Windows 侧的观测手段，不是字节比对。

> **原文**（[instruction.md:38-39](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/instruction.md#L38-L39>)）
> ```
> 这里的“值写入/同数值重写”指 Windows 实际产生值变更通知的操作，例如保留逻辑数值但改变注册表值类型。
> 类型与字节内容均完全相同的幂等写入可能被 Windows 合并，不要求为系统未产生的通知补发回调。
> ```
> **解释**：这是全篇最关键的一句——把"同值不同**类型**改写"定义为可观测写入。
> 它既是题面给候选的提示，也是验证层反伪造判据的依据（见下）。

> **原文**（[instruction.md:47-48](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/instruction.md#L47-L48>)）
> ```
> 只能用 net8.0-windows 自带的 BCL 与操作系统原生能力。
> 不得保留、也不得改回任何形式的周期性轮询来判断「有没有变化」。
> ```
> **解释**：禁用轮询是**硬约束**，但评测器不扫源码，而是用"空闲 CPU 增量"这种运行时可观测证据来判定。

- **是否点名具体 Windows 对象/机制**：是。`RegistryNotify` / `RegNotifyChangeKeyValue`（隐含）、
  注册表值类型、键 last-write 时间与 `DateTimeKind.Utc`、跨进程写。
- **是否声明"不需要其他操作系统版本"**：**没有**。反而在
  [instruction.md:46-47](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/instruction.md#L46-L47>)
  强调"判分环境全程断网，只有已 vendored 的离线包可用"，把运行环境收紧到 `net8.0-windows`。

### 环境层

- 运行平台声明：[task.toml:8](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/task.toml#L8>)
  `tags = ["coding", "windows", "registry", "dotnet"]`；
  [task.toml:19](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/task.toml#L19>) `os = "windows"`。
- **显式的 Windows 断言 + 架构断言**（[validate_environment.ps1:77-82](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/environment/validate_environment.ps1#L77-L82>)）：
  ```powershell
  $isWindows = $true
  try { $isWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows) } catch { $isWindows = ($env:OS -eq 'Windows_NT') }
  [void](Report-Check $isWindows 'os_is_windows' ("RuntimeInformation says Windows={0}, OSDescription={1}" -f $isWindows, [System.Environment]::OSVersion.VersionString))

  $arch = [string]$env:PROCESSOR_ARCHITECTURE
  [void](Report-Check ($arch -eq 'AMD64') 'os_architecture_x64' "PROCESSOR_ARCHITECTURE=$arch (the frozen contract requires an x64 registry view and x64 build)")
  ```
- **机制探针**：不是"能读注册表就行"，而是**当场写三种类型并读回**，失败即环境不合格
  （[validate_environment.ps1:125-147](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/environment/validate_environment.ps1#L125-L147>)）：
  ```powershell
  $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Registry64)
      $probe = $hive.CreateSubKey($script:RegistryProbeSubKey, $true)
          $probe.SetValue('Probe', 'harbor', [Microsoft.Win32.RegistryValueKind]::String)
          $probe.SetValue('ProbeQ', [long]9000000000, [Microsoft.Win32.RegistryValueKind]::QWord)
          $probe.SetValue('ProbeE', '%LOCALAPPDATA%\LiteMonitor', [Microsoft.Win32.RegistryValueKind]::ExpandString)
          $read = $hive.OpenSubKey($script:RegistryProbeSubKey, $false)
          $registryOk = ($null -ne $read -and [string]$read.GetValue('Probe') -eq 'harbor')
      $hive.DeleteSubKeyTree($script:RegistryProbeSubKey, $false)
      $registryDetail = 'HKCU writable in the 64-bit view (REG_SZ / REG_QWORD / REG_EXPAND_SZ probe created, read back and removed)'
  ...
  [void](Report-Check $registryOk 'hkc_registry_writable' $registryDetail)
  ```
- 探针键位置与清理契约集中在
  [env_common.ps1:42-43](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/environment/env_common.ps1#L42-L43>)
  （`Software\LiteMonitor`、`Software\HarborEnvironmentProbe`）；
  清理用 `RegistryView::Registry64` 删整棵树
  [env_common.ps1:231-237](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/environment/env_common.ps1#L231-L237>)；
  残留检查在 [env_common.ps1:407-414](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/environment/env_common.ps1#L407-L414>)。
  清理脚本还会核对清理前后存在性
  （[cleanup.ps1:92-116](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/environment/cleanup.ps1#L92-L116>)）。
- **保障**：`os_is_windows` / `hkc_registry_writable` 任一失败 → 环境不合格（exit 2 → INVALID），
  因此 **Linux/容器里跑必然失败**，而不是"凑巧也能评分"。

### 验证层

验证层由 C# 评测器（`tests/LiteMonitor.Evaluator`）实现，33 个必过用例
（[rubric.json:6-240](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/rubric.json#L6-L240>)）。
它**不读候选源码**，全部靠"评测器自己作为另一个 Windows 对象使用者"来观测。

**(1) 同值换类型：把"值对比轮询器"直接判死**（02.1 的核心反伪造判据）
[NotifyChecks.cs:246-259](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L246-L259>)：
```csharp
// Windows does not advance a key's last-write stamp for a byte-for-byte
// same-kind rewrite, so that operation is not observable through
// REG_NOTIFY_CHANGE_LAST_SET.  Rewrite the same logical value with a
// different registry kind instead; the stored value is still 4242, but
// the metadata change is a real registry write.  This remains a
// mechanism-specific control against a Generation/value-diff poller.
w.Sink.Reset();
NotifyFixture.WriteValue(NotifyFixture.Status, "Seed", 4242L, RegistryValueKind.QWord);
int sameValue = w.AwaitCallback();
Harness.Assert(sameValue >= 0,
    "rewriting Seed with the identical value produced no callback; " +
    "the implementation is behaving like a value-difference poller");
```
同样的手法在集成层再用一次（Generation 不变、主题名逐字符不变，只把 `String` 换成 `ExpandString`）
[IntegrationChecks.cs:69-80](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/IntegrationChecks.cs#L69-L80>)：
```csharp
// ... this is an observable write and still distinguishes the event-driven
// path from a poller that only compares Generation or the value.
sink.Reset();
NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
    "MatrixGreen_Terminal", RegistryValueKind.ExpandString);
int sameValue = NotifyFixture.WaitUntil(() => sink.Count > 0, 2500);
Harness.Assert(sameValue >= 0,
    "rewriting the same mirror value produced no callback; " +
    "StartRefresher is behaving like a value-difference poller");
```

**(2) 真实跨进程写注册表**
- 评测器夹具统一通过 64 位视图打开 HKCU 并 `Flush()`
  （[NotifyChecks.cs:22-53](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L22-L53>)）：
  ```csharp
  public static RegistryKey Base() =>
      RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry64);
  ...
  public static void WriteValue(string sub, string name, object value, RegistryValueKind kind)
  {
      using RegistryKey b = Base();
      using RegistryKey? k = b.CreateSubKey(sub, writable: true);
      Harness.Precondition(k is not null, "evaluator fixture could not create HKCU\\" + sub);
      k!.SetValue(name, value, kind);
      k.Flush();
  }
  ```
- **第二个 OS 进程**作为独立发布者，证明镜像不是进程内缓存
  （[Program.cs:360-370](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/Program.cs#L360-L370>)）：
  ```csharp
  /// <summary>
  /// Publishes the mirror once from a SEPARATE OS process, so the system_state suite can
  /// prove the mirror is machine-wide state and not an in-process cache.
  /// </summary>
  private static int ModePublishChild()
  {
      bool ok = StatusMirror.Publish(new StatusSnapshot(false, 7, "Dracula_Vampire", 987654321L));
  ```
  由 [SystemStateChecks.cs:25-48](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/SystemStateChecks.cs#L25-L48>)
  的 `SS_T1_mirror_is_machine_state_visible_from_a_second_process` 消费。

**(3) 真实空闲 CPU 量测 + 反"睡死"控制组**
[NotifyChecks.cs:590-615](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L590-L615>)：
```csharp
NotifyFixture.WriteValue(NotifyFixture.Status, "PreIdle", 1, RegistryValueKind.DWord);
Harness.Assert(w.AwaitCallback() >= 0,
    "the watcher was already silent before the idle window, so a low CPU delta would be vacuous");

Process p = Process.GetCurrentProcess();
p.Refresh();
TimeSpan before = p.TotalProcessorTime;
Thread.Sleep(5000);
p.Refresh();
double cpuMs = (p.TotalProcessorTime - before).TotalMilliseconds;

w.Sink.Reset();
NotifyFixture.WriteValue(NotifyFixture.Status, "PostIdle", 1, RegistryValueKind.DWord);
int after = w.AwaitCallback();
Harness.Assert(after >= 0, "the watcher was alive before the 5s idle window but dead afterwards");
Harness.Assert(cpuMs >= 0 && cpuMs < 40.0,
    "an idle watcher consumed " + cpuMs.ToString("F1", CultureInfo.InvariantCulture) +
    "ms of process CPU in 5s, the contract requires < 40ms");
```
> 判据形态值得抄：**低 CPU 只有在"证明它仍然活着"之后才有意义**（前 595-597、后 607-609 两次写入）。

**(4) 真实删除 + 重建键后的自愈（stale handle 判死）**
[NotifyChecks.cs:510-534](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L510-L534>)：
```csharp
NotifyFixture.DeleteTree(NotifyFixture.Status);
Thread.Sleep(600);
NotifyFixture.WriteValue(NotifyFixture.Status, "Recreated", 0, RegistryValueKind.DWord);
...
Harness.Assert(fired >= 0,
    "after HKCU\\" + NotifyFixture.Status +
    " was deleted and recreated the watcher stayed silent for 5s - it is still holding the stale key handle");
```
整棵树被 Purge 再重发布
[NotifyChecks.cs:554-585](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L554-L585>)：
```csharp
// StatusMirror.Purge() removes the WHOLE HKCU\Software\LiteMonitor tree (uninstall / reset),
// and a later Publish() brings the mirror back. The caller only ever gets one handle from
// Watch, so that handle has to survive the parent key disappearing as well.
NotifyFixture.DeleteTree(NotifyFixture.Root);
...
Harness.Assert(fired >= 0,
    "after the whole HKCU\\" + NotifyFixture.Root +
    " tree was removed and the mirror was published again the watcher stayed silent for 6s - " +
    "it gave up permanently instead of re-attaching to the recreated key");
```

**(5) 最后写入时间：时间刻度 + `DateTimeKind` + "不得用当前时间冒充"**
[NotifyChecks.cs:689-691](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L689-L691>)、
[703-710](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L703-L710>)、
[722-732](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L722-L732>)、
[749-753](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L749-L753>)：
```csharp
Harness.Assert(value.Kind == DateTimeKind.Utc,
    "the returned DateTime.Kind was " + value.Kind +
    "; FILETIME is a UTC count so Kind must be exactly Utc");
...
Harness.Assert(skew < 120.0,
    "... interpreting FILETIME as local time is off by the whole UTC offset");
...
Harness.Assert(unchangedOk && unchanged == t1,
    "the recorded key timestamp changed while no registry write occurred; current wall-clock time is not the key's last-write time");
...
Harness.Assert(delta >= 1.0 && delta <= 3.0,
    "two writes 1.5s apart produced a last-write delta of " + ... +
    "s; expected 1.0..3.0s, so the 100-nanosecond FILETIME tick conversion is wrong");
```
这三条分别封死"Kind 不对"、"按本地时间解释"、"用 `DateTime.UtcNow` 冒充血统记录"、"FILETIME 刻度换算错"。

**(6) 回调异常必须被候选吞掉：用子进程证明 CLR 没被炸掉**
[NotifyChecks.cs:536-551](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L536-L551>)：
```csharp
// Runs in a child process: an implementation that lets the callback
// exception escape onto a system thread kills the CLR, and that must
// not be able to take the whole evaluator down with it.
(int exitCode, string stdout) = Native.RunSelf("--mode=notifythrow", 180000);
...
Harness.Assert(marker != "",
    "the child process died without reporting (exitCode=" + exitCode +
    "); a callback exception escaped onto a system thread and crashed the CLR. output tail: " + tail);
```
隔离执行 + 可信回执的机制见
[test_fail_to_pass.ps1:110-124](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/test_fail_to_pass.ps1#L110-L124>)
（含 0xC0000005 访问违例被单独识别为 fail 而不是 infrastructure）。

**(7) 缺失键不得代为创建 / 只监视目标键本身**
[NotifyChecks.cs:626-637](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/NotifyChecks.cs#L626-L637>)：
```csharp
try { handle = RegistryNotify.Watch(sink.OnChange, false); }
catch (Exception ex) { error = ex.GetType().Name + ": " + ex.Message; }

bool created = NotifyFixture.Exists(NotifyFixture.Status);
...
Harness.Assert(handle is null, "Watch returned a handle even though HKCU\\" + NotifyFixture.Status + " does not exist");
Harness.Assert(!created, "Watch created HKCU\\" + NotifyFixture.Status + " although the contract forbids creating the key");
```
作用域与退订见 [IntegrationChecks.cs:132-137](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.1/tests/LiteMonitor.Evaluator/IntegrationChecks.cs#L132-L137>)。

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| 保留 200ms 轮询、只把"比较内容"改成"比较 last-write 时间" | `W_T21`（5s 空闲 CPU > 40ms）、`W_T05`/`I_T1`（同值换类型不回调） |
| 用 `Task.Delay` + 每次重开键读值的"伪事件" | 同上；另外 `W_T08` 的 40 连写突发后必须仍活着 |
| 订阅一次就不再 re-arm | `W_T07`（5 次间隔 200ms 必须 ≥5 次回调）、`W_T08`、`I_T2` |
| 只用 `DateTime.UtcNow` 返回"最后写入时间" | `L_T03`（无写入时不得变化）、`L_T04`（1.5s 间隔 delta 必须 1.0–3.0s） |
| 持有旧键句柄、键被删就永久沉默 | `W_T19`、`W_T24`、`I_T4` |
| 回调里让异常逃逸（或直接不 try/catch） | `W_T20`（子进程 CLR 存活 + 必须先报告 marker） |
| 键不存在时顺手创建 | `W_T22`、`L_T05`（`Exists` 前置 + 断言 `!created`） |

强模型之所以能过：题目把"机制语义"写清楚了（含"同值换类型算一次写入"这种边界），
契约完整、判据可推导，不需要猜；但每一条都对实现路径有硬要求。

### 机制关键词

`RegNotifyChangeKeyValue`、`REG_NOTIFY_CHANGE_LAST_SET`、`RegOpenKeyEx`、`KEY_NOTIFY`、`KEY_WOW64_64KEY`、
`RegistryView.Registry64`、`HKCU\Software\LiteMonitor`、`RegistryValueKind` 同值换类型、
键 last-write `FILETIME`、`DateTimeKind.Utc`、`Process.TotalProcessorTime`、空闲 CPU 上限、
re-arm / 自愈、stale key handle、`Purge` + 重新 `Publish`、回调异常不得逃逸。

---

## 002.2 windows-d6-0007：NTFS 文件身份 / 安全描述符 / 原生 64 位注册表视图 / 崩溃回滚

### 题面层

题面开头就把运行环境钉死成一种具体形态，并点明 32 位进程与原生 64 位注册表视图的错位——这是**只有 Windows 才有**的坑。

> **原文**（[instruction.md:6](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/instruction.md#L6>)）
> ```
> 本轮冻结真实 Windows Server Core LTSC 2022 x64 container、zh-CN、PowerShell 5.1、.NET Framework 4.8。使用系统 Framework v4.0.30319 编译器，C# 5，产物必须为 x86。无外部包，无 shell/网络工具。
> ```
> **解释**：OS 版本、区域、Shell 版本、编译器、目标架构全部冻结。

> **原文**（[instruction.md:8](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/instruction.md#L8>)）
> ```
> 注册表基路径由环境变量 EVIDENCE_MIRROR_REGISTRY_ROOT 提供，位于 HKLM\SOFTWARE\Northgate\EvidenceMirrorBench\windows-d6-0007\<run-id>；基线的 RootKeyPath 已读取该配置。监控服务读取此基路径的原生 64 位视图 Cases\<CaseId>，不是当前 x86 进程的默认视图。
> ```
> **解释**：**版本红移（WOW64 registry redirection）**被显式做进题：x86 进程默认落在 `WOW6432Node`，
> 而权威记录必须在原生 64 位视图里，且只能有一份。

> **原文**（[instruction.md:13](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/instruction.md#L13>)）
> ```
> 每个文件的全部主流和命名流、文件名、所有者、DACL（含保护和继承状态）、SACL 审计规则、创建/最后写入 UTC、稀疏/压缩属性和存储形态、硬链接关系及链接数均保持。文件 ID 数值、物理簇、访问时间、空目录和重解析点不在范围。
> ```
> **解释**：把"NTFS 等价"精确定义为一组 Windows 侧可观测项，并明确排除项（避免不可判定）。

> **原文**（[instruction.md:17](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/instruction.md#L17>)）
> ```
> 权威记录只能有一份：在上述 HKLM 原生64视图的 Cases\<CaseId> 下，FileCount 为 DWORD，其余 RootHash/MirrorRoot/CompletedUtc 为 REG_SZ；恰好这四个值。移除本案重定向32视图的陈旧记录，不能动别的案卷。report 从同一权威位置读取。
> ```
> **解释**：直接规定**注册表值类型**与"恰好四个值"，为"字符串近似"以外的真实类型判定提供依据。

> **原文**（[instruction.md:20](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/instruction.md#L20>)）
> ```
> SACL 保留包括审计主体、访问掩码、成功/失败审计标志、继承/传播标志、显式/继承状态及 SACL 保护状态。同样，DACL 的显式/继承 ACE 状态不能被只保留权限掩码替代。……运行账户为本机管理员，具备启用备份、还原和安全审计所需的 Windows 特权；不得借此访问其他轮次或题目的数据。
> ```
> **解释**：明文写"**不能被只保留权限掩码替代**"——直接把"近似实现"列为不合格。

> **原文**（[instruction.md:14](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/instruction.md#L14>)）
> ```
> 长路径、2,200,000,000 字节稀疏录像必须在 x86 地址空间中正确处理，不截断、不遗漏；文件计数包括硬链接各名字。
> ```
> **解释**：2.2 GB 稀疏文件 + x86 地址空间 + `\\?\` 长路径，三者叠加是纯 Windows/NTFS 约束。

- **是否点名具体 Windows 对象/机制**：是，且非常密集：HKLM 原生 64 位视图、`REG_SZ`/`DWORD`、
  NTFS ADS、硬链接与链接数、稀疏/压缩属性、DACL/SACL 的继承与保护状态、备份/还原/安全审计特权、x86 产物。
- **是否声明"不需要其他操作系统版本"**：**没有**；正相反，环境被冻结到 Windows Server Core LTSC 2022 x64 +
  .NET Framework 4.8 + x86，且平台偏离时判 INVALID。

### 环境层

- **镜像与 SDK 版本硬校验**（[Dockerfile:2](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/Dockerfile#L2>)、
  [Dockerfile:8](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/Dockerfile#L8>)）：
  ```dockerfile
  FROM mcr.microsoft.com/dotnet/sdk:8.0.424-windowsservercore-ltsc2022@sha256:fa7a4d07b9...
  RUN if ((dotnet --version) -ne '8.0.424') { throw 'SDK version mismatch' }
  ```
- **四条"非 Windows / 非 NTFS / 非管理员必然失败"的硬门槛**
  （[validate_environment.ps1:3-11](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/validate_environment.ps1#L3-L11>)）：
  ```powershell
  if (-not [Environment]::Is64BitOperatingSystem) {throw '64-bit Windows required'}
  $csc=Join-Path $env:SystemRoot 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
  if (-not (Test-Path -LiteralPath $csc)) {throw 'Framework compiler missing'}
  $drive=New-Object IO.DriveInfo([IO.Path]::GetPathRoot($WorkspaceRoot))
  if ($drive.DriveFormat -ne 'NTFS') {throw 'NTFS required'}
  $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {throw 'Elevated Windows token required'}
  $fixture=Join-Path $WorkspaceRoot 'state\cases\CASE-2231'
  if (@([IO.Directory]::GetFiles(('\\?\'+$fixture),'*','AllDirectories')).Count -ne 16) {throw 'Incomplete field fixture'}
  ```
  > 注意最后一行：连**夹具文件数**都作为环境门槛，且用 `\\?\` 前缀枚举长路径目录。
- **用真实 Windows 工具造 NTFS 形状**（[provision.ps1:13-34](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/provision.ps1#L13-L34>)）：
  ```powershell
  & fsutil.exe sparse setflag $recording | Out-Null
  ...
  $stream=[IO.File]::Open($recording,'Open','Write','ReadWrite')
  try {$stream.SetLength(2200000000)} finally {$stream.Dispose()}
  [IO.File]::SetCreationTimeUtc($recording,$created)
  [IO.File]::SetLastWriteTimeUtc($recording,$written)
  & fsutil.exe hardlink create (Join-Path $field 'names\intake-manifest.bin') (Join-Path $field 'intake\intake-manifest.bin') | Out-Null
  ...
  & compact.exe /c $compressed | Out-Null
  ```
  安全属性由 [apply_case_security.ps1](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/apply_case_security.ps1>)
  以当前用户 SID 施加（[provision.ps1:33-35](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/provision.ps1#L33-L35>)）。
- **把 SDDL / 流 / 属性写进运行期清单**（[provision.ps1:36-45](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/provision.ps1#L36-L45>)）：
  ```powershell
  $security=[IO.File]::GetAccessControl($file,[Security.AccessControl.AccessControlSections]::All)
  $streams=@(Get-Item -LiteralPath $file -Stream * | ForEach-Object {@{name=$_.Stream;length=$_.Length}})
  $rows+=@{path=...;length=$info.Length;attributes=[string]$info.Attributes;streams=$streams;security_sddl=$security.GetSecurityDescriptorSddlForm(...)}
  ```
- **注册表基路径按 run-id 注入**（[run_tests.ps1:10](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/run_tests.ps1#L10>)）：
  ```powershell
  $env:EVIDENCE_MIRROR_REGISTRY_ROOT='SOFTWARE\Northgate\EvidenceMirrorBench\windows-d6-0007\'+(Split-Path -Leaf $workspace)
  ```
- 工作区路径白名单，防跑错目录（[prepare.ps1:4](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/environment/prepare.ps1#L4>)）。

### 验证层

**(1) 安全描述符：用 ACE 二进制指纹 + 继承位分组，而不是权限掩码**
[candidate_contract.ps1:9-36](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/candidate_contract.ps1#L9-L36>)：
```powershell
function NG-AceBytes($Ace) {
    $bytes = New-Object byte[] $Ace.BinaryLength
    $Ace.GetBinaryForm($bytes, 0)
    return [Convert]::ToBase64String($bytes)
}
function NG-DaclBlocks($Acl) {
    ...
        if ($ace.AceType -eq [Security.AccessControl.AceType]::AccessAllowed) {
            $inherited = [int]$ace.AceFlags -band 16
            ...
            $blocks.Add('ALLOW:' + $inherited + ':' + ($sorted -join ','))
        } else {
            $blocks.Add('FIXED:' + (NG-AceBytes $ace))
```
配合指纹函数（[test_fail_to_pass.ps1:179-187](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L179-L187>)）：
```powershell
$sec = [System.IO.File]::GetAccessControl($fullExt, $sections)
$owner = $sec.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
$protected = [bool]$sec.AreAccessRulesProtected
$descriptor = [Security.AccessControl.RawSecurityDescriptor]::new($sec.GetSecurityDescriptorBinaryForm(), 0)
return ($owner + '#' + $protected + '#' + (NG-DaclBlocks $descriptor.DiscretionaryAcl))
```
SACL 用**逐条审计规则五元组 + 保护位**
（[test_fail_to_pass.ps1:147-153](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L147-L153>)）：
```powershell
$rules = @($sec.GetAuditRules($true, $true, [System.Security.Principal.SecurityIdentifier]) | ForEach-Object {
    '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value, [int]$_.FileSystemRights, [int]$_.AuditFlags, [int]$_.InheritanceFlags, [int]$_.PropagationFlags, $_.IsInherited
} | Sort-Object)
return ([bool]$sec.AreAuditRulesProtected).ToString() + '#' + ($rules -join ';')
```
> 业务侧注释明确写了为什么源上必须有既有审计规则
> （[test_fail_to_pass.ps1:300](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L300>)：
> `throw "[INVALID] 源文件 $rel 上没有既有审计规则（构建期安全属性未落地）"`）——
> 夹具没落地就当环境问题，不算候选失败。

**(2) 文件身份：`GetFileInformationByHandle` 的卷序列号 + 文件索引 + 链接数**
[test_fail_to_pass.ps1:49](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L49>)、
[81](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L81>)：
```csharp
[StructLayout(LayoutKind.Sequential)] public struct BHFI { ... public uint NumberOfLinks; public uint FileIndexHigh; public uint FileIndexLow; }
...
public static string IdOf(string path) { IntPtr h = CreateFileN(path, 0x80, 3, IntPtr.Zero, 3, 0x02000000, IntPtr.Zero); ... GetFileInformationByHandle(h, out i); ... return i.VolumeSerialNumber.ToString() + ":" + (((ulong)i.FileIndexHigh << 32) | i.FileIndexLow).ToString() + ":" + i.NumberOfLinks.ToString(); }
```
硬链接保真用例（[test_fail_to_pass.ps1:798-819](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L798-L819>)）：
```powershell
$srcId = NG-FileIdentity $srcPrim
if ($srcId -ne (NG-FileIdentity $srcAlias)) { throw "[INVALID] 源里 $primRel 与 $aliasRel 不是同一份数据的两个名字（冻结输入形状异常）" }
...
if ($mirPrimId -ne $mirAliasId) {
    throw ("镜像里 $primRel 与 $aliasRel 变成了两份互不相干的数据（标识 $mirPrimId 与 $mirAliasId）：源里它们是同一份数据的两个名字，忠实副本必须保住这个身份")
}
$mirLinks = [int]($mirPrimId.Split(':')[2]); $srcLinks = [int]($srcId.Split(':')[2])
if ($mirLinks -ne $srcLinks) { throw "镜像里这份数据的名字数=$mirLinks，源里是 $srcLinks" }
```

**(3) 注册表双视图 + 原生值类型**
真实记录断言（[test_fail_to_pass.ps1:634-656](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L634-L656>)）：
```powershell
$k = $base64.OpenSubKey($sub)
if ($null -eq $k) { throw "64 位监控台读取的原生 64 位注册表视图里没有本案封存记录（HKLM\$sub）；记录被写进了别的视图" }
...
if ($names -contains 'LegacyDigest') { throw '封存记录里残留了本次封存之前就存在的值 LegacyDigest；每次封存都必须重建这份记录，而不是往旧键上叠加' }
...
if ($k.GetValueKind('FileCount') -ne [Microsoft.Win32.RegistryValueKind]::DWord) { throw "FileCount 的值类型是 $($k.GetValueKind('FileCount'))，契约要求 REG_DWORD" }
foreach ($vn in @('RootHash', 'MirrorRoot', 'CompletedUtc')) {
    if ($k.GetValueKind($vn) -ne [Microsoft.Win32.RegistryValueKind]::String) { throw "$vn 的值类型是 $($k.GetValueKind($vn))，契约要求 REG_SZ" }
}
...
$q = NG-RunNative -FilePath 'reg.exe' -Arguments @('query', ('HKLM\' + $sub), '/reg:64')
```
32 位重定向视图必须**没有**记录（[test_fail_to_pass.ps1:660-669](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L660-L669>)）：
```powershell
$base32 = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry32')
$k = $base32.OpenSubKey($sub)
if ($null -ne $k) {
    throw "32 位重定向视图里也出现了本案的封存记录（HKLM\SOFTWARE\WOW6432Node\...）；同一案卷只允许一份权威记录，..."
}
```
六种注册表类型预置 + 原生读取（[test_batch.ps1:72-77](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_batch.ps1#L72-L77>)、
[test_batch.ps1:11-12](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_batch.ps1#L11-L12>)）：
```powershell
$key.SetValue('Text','old-'+$view,[Microsoft.Win32.RegistryValueKind]::String)
$key.SetValue('Expand','%SystemRoot%\unchanged',[Microsoft.Win32.RegistryValueKind]::ExpandString)
$key.SetValue('Many',[string[]]@('first','','last'),[Microsoft.Win32.RegistryValueKind]::MultiString)
$key.SetValue('Count',[int]-7,[Microsoft.Win32.RegistryValueKind]::DWord)
$key.SetValue('Wide',[long]1099511627781,[Microsoft.Win32.RegistryValueKind]::QWord)
$key.SetValue('Bytes',[byte[]]@(0,255,17,2),[Microsoft.Win32.RegistryValueKind]::Binary)
...
$value = $key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$rows += ($view+'|'+$name+'|'+$key.GetValueKind($name)+'|'+(ConvertTo-Json -InputObject $value -Compress))
```
> 批量用例先用**两视图各写一份旧记录**，然后要求候选成功时"恰好"清掉本案的陈旧项、保留另一案卷的
> sentinel（[test_additional.ps1:68-75](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_additional.ps1#L68-L75>)、
> [test_additional.ps1:101](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_additional.ps1#L101>)、
> [test_additional.ps1:131](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_additional.ps1#L131>)）。

**(4) 稀疏 / 压缩存储形态（用分配字节数而不是"属性位"糊弄）**
[test_fail_to_pass.ps1:744-763](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L744-L763>)、
[765-790](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L765-L790>)：
```powershell
if (([int]$mirInfo.Attributes -band [int][System.IO.FileAttributes]::SparseFile) -eq 0) { ... }
if ($mirAlloc -gt $script:NG_SparseAllocatedCeiling) { ... }   # 4194304
...
if (([int]$mirInfo.Attributes -band [int][System.IO.FileAttributes]::Compressed) -eq 0) { ... }
# Windows lazy-writer can publish the compressed allocation after the ...
```
分配量来自 P/Invoke `GetCompressedFileSizeW`
（[test_fail_to_pass.ps1:53](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L53>)、
[80](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_fail_to_pass.ps1#L80>)）。

**(5) 崩溃恢复：checkpoint 握手 + 强制终止 + 新进程 recover**
[test_batch.ps1:208-256](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_batch.ps1#L208-L256>)：
```powershell
$start.EnvironmentVariables['EVIDENCE_MIRROR_PAUSE'] = $Point
$start.EnvironmentVariables['EVIDENCE_MIRROR_SIGNAL'] = $signal
$start.EnvironmentVariables['EVIDENCE_MIRROR_RELEASE'] = $signal+'.release'
...
        if (-not $observed) { throw 'Candidate did not provide the requested live checkpoint handshake' }
        if ([IO.File]::ReadAllText($signal) -cne $Point) { throw 'Candidate checkpoint receipt is incorrect' }
        if ($Point -eq 'prepared') { NG-BatchAssertOld $Fixture }
...
    } finally {
        $killed = -not $process.HasExited
        if ($killed) { $process.Kill() }
```
六个注入点与"恢复后应处于的状态"（[test_batch.ps1:329-334](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_batch.ps1#L329-L334>)）：
```powershell
function Test-F2P_BatchPreparedCrash { NG-BatchCrashRecover 'prepared' }
function Test-F2P_BatchFirstReplacementCrash { NG-BatchCrashRecover 'replaced:1' }
function Test-F2P_BatchSecondReplacementCrash { NG-BatchCrashRecover 'replaced:2' }
function Test-F2P_BatchFirstPublicationCrash { NG-BatchCrashRecover 'published:1' }
function Test-F2P_BatchSecondPublicationCrash { NG-BatchCrashRecover 'published:2' }
function Test-F2P_BatchCommittedCrash { NG-BatchCrashRecover 'committed' 'COMMITTED' }
```
> 这是**跨进程真实崩溃**语义：不是模拟异常，而是 `Kill()` 之后由新进程 `recover` 断言回到
> `ROLLED_BACK` 或 `COMMITTED`。

**(6) 产物必须真是 x86**（读 PE 头 `/CLR` 的 32BITREQUIRED 位）
[test_pass_to_pass.ps1:51-65](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.2/tests/test_pass_to_pass.ps1#L51-L65>)：
```powershell
$peOffset = [System.BitConverter]::ToInt32($bytes, 60)
$cliRva = [BitConverter]::ToUInt32($bytes, $optional + 96 + 14 * 8)
...
if ($cliOffset -lt 0 -or ([BitConverter]::ToUInt32($bytes, $cliOffset + 16) -band 2) -eq 0) { throw 'CLR 32BITREQUIRED flag is missing; AnyCPU is not x86' }
```

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| `Copy-Item` / `File.Copy` 复制内容，其他元数据不管 | DACL/SACL 指纹、时间、属性、流、硬链接五组用例全挂 |
| 只对权限掩码（`FileSystemRights`）取并集比较 | `NG-DaclBlocks` 的 ACE 二进制 + 继承位分组 |
| 用字符串比路径判断"同一文件" | `NG-FileIdentity`（卷序列号+文件索引+链接数） |
| 在 x86 进程里直接写 `HKLM\SOFTWARE\...` | 记录落进 `WOW6432Node`，`SealRecordVisibleInNative64BitView` 失败、`...AbsentFromRedirected32BitView` 也失败 |
| 用 `Set-ItemProperty` 写 `REG_SZ` 字符串了事 | `GetValueKind` 类型断言 + `reg.exe /reg:64` 复核 |
| 复制完就 `SetLength`/重写文件 | 稀疏分配上限 4 MiB、压缩分配 ≤ 长度/4 断言失败 |
| 失败时"先删旧记录再说" | `run_public_failure` 路径与 `Test-F2P_AtomicRecordPublicationFailure`（旧记录两视图都必须保留） |
| 没有 checkpoint 握手（无法在崩溃点观测） | `throw 'Candidate did not provide the requested live checkpoint handshake'` |

强模型能过的原因：题面把协议（摘要规则、CLI、记录形状、checkpoint 点）**完整公开**，
难度落在"必须真用 NTFS/注册表/Win32 能力"，而不是猜规格。

### 机制关键词

`EVIDENCE_MIRROR_REGISTRY_ROOT`、HKLM 原生 64 位视图 vs `Registry32`/`WOW6432Node`、`reg.exe /reg:64`、
`REG_SZ`/`REG_DWORD`/`REG_EXPAND_SZ`/`REG_MULTI_SZ`/`REG_QWORD`/`REG_BINARY`、
`GetFileInformationByHandle`（`VolumeSerialNumber`/`FileIndex`/`NumberOfLinks`）、
`GetCompressedFileSizeW`、`GetSecurityDescriptorBinaryForm`+`RawSecurityDescriptor`、
`AreAccessRulesProtected`/`AreAuditRulesProtected`、`GetAuditRules`、`fsutil sparse setflag`、
`fsutil hardlink create`、`compact.exe /c`、`\\?\` 长路径、2.2 GB 稀疏录像、x86 `/CLR 32BITREQUIRED`、
checkpoint 崩溃恢复。

---

## 002.6 windows-powershell-ads-001：Zone.Identifier ADS / 同一文件对象 / 双 PowerShell 宿主 / Atomic 回滚

### 题面层

> **原文**（[instruction.md:5](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L5>)）
> ```
> 项目需要在 Windows 上批量清理下载文件留下的 NTFS `Zone.Identifier` 来源标记。现有脚本只要看到文件存在就返回成功。
> ```
> **解释**：任务对象本身就是 NTFS 备用数据流——非 NTFS 卷上不存在这个概念。

> **原文**（[instruction.md:16](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L16>)）
> ```
> 移除来源标记不能删除或重建主文件。主文件必须保持同一个文件对象，内容、长度、SHA256、创建时间、最后写入时间和原有属性都必须保持不变；除目标流以外的所有备用数据流必须保持原样。只读、隐藏等属性组合也必须在成功后恢复。
> ```
> **解释**："同一个文件对象"是 Windows 文件句柄语义（文件 ID 不变），不是内容哈希相等。

> **原文**（[instruction.md:23](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L23>) 与
> [instruction.md:24](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L24>)）
> ```
> 11. `-AuditPath` 不得与任一输入文件是**同一文件对象**。判定必须基于文件身份，而不是路径字符串：同一文件的硬链接、不同大小写、相对/绝对或带 `.\` 前缀的不同写法都算冲突，必须在删除任何目标流之前失败；不得只比较两个路径文本是否相等。
> 12. 同一物理文件以不同写法（绝对路径、相对路径、`.\` 前缀、硬链接）在同一批次出现时，必须按**文件身份**处理而不是按路径字符串处理……
> ```
> **解释**：明文禁止"路径字符串近似"，把判据推向文件身份。

> **原文**（[instruction.md:22](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L22>)）
> ```
> 10. 父目录链也是输入的一部分：输入路径的**任一父目录**（含中间层级）是 Reparse Point（Junction 或符号链接）时，该输入必须返回 `Failed`……不允许只检查叶节点。
> ```
> **解释**：Reparse Point / Junction 是 NTFS 独有构造。

> **原文**（[instruction.md:27](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L27>)）
> ```
> 15. 必须接受扩展长度前缀写法（`\\?\` 与 `\\?\UNC\`）……**总长度超过 260 个字符的路径不在本要求范围内**（Windows PowerShell 5.1 所在 .NET Framework 不支持长路径，属平台限制）。
> ```
> **解释**：注意这不是"不需要 Windows"的免责句，而是**把 Windows 平台限制写进契约边界**（可判定性说明）。

> **原文**（[instruction.md:9](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L9>) 与
> [instruction.md:20](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/instruction.md#L20>)）
> ```
> 完善 `workspace/src/ZoneMarkCleaner.ps1` 中的 `Clear-ZoneIdentifier` 函数，使它在 Windows PowerShell 5.1 和 PowerShell 7 上可用。
> ...
> 8. 提交过程中任何一步失败，都必须把本批已经删掉的目标流尽力恢复回来，并把已触碰文件的属性和时间还原，不能留下半批结果。
> ```
> **解释**：双宿主兼容 + 真实事务回滚是本题的两条正交难度轴。

- **是否点名具体 Windows 对象/机制**：是（NTFS ADS、Reparse Point、文件身份、`\\?\` 前缀、PS 5.1/7 差异）。
- **是否声明"不需要其他操作系统版本"**：**没有**；只在长路径上声明了 Windows PowerShell 5.1 的平台限制。

### 环境层

- **非 Windows 直接 throw**（[validate_environment.ps1:11-13](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/environment/validate_environment.ps1#L11-L13>)）：
  ```powershell
  if ($env:OS -ne 'Windows_NT') {
      throw 'This pilot requires Windows.'
  }
  ```
- **机制探针：真造一个 ADS，读不到就失败**（[validate_environment.ps1:15-21](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/environment/validate_environment.ps1#L15-L21>)）：
  ```powershell
  New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null
  Set-Content -LiteralPath $probeFile -Value 'probe' -Encoding UTF8
  Set-Content -LiteralPath $probeFile -Stream 'Zone.Identifier' -Value 'ZoneId=3' -Encoding UTF8
  $stream = Get-Item -LiteralPath $probeFile -Stream 'Zone.Identifier' -ErrorAction SilentlyContinue
  if ($null -eq $stream) {
      throw 'NTFS alternate data streams are unavailable.'
  }
  ```
  > 这正是"非 NTFS 必然失败"的显式保障（FAT/ReFS 或不支持 ADS 的宿主上环境直接 INVALID）。
- **双宿主矩阵**：镜像/普通用户约束见
  [Dockerfile:1](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/environment/Dockerfile#L1>)（私有 Windows 镜像）、
  [adapter.toml:6](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/environment/adapter.toml#L6>)（`privilege = "standard-user"`，本题**不需要管理员**，这也是差异点）。
  双宿主由 [run_matrix.ps1:10-18](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_matrix.ps1#L10-L18>) 强制：
  ```powershell
  $shells = @(
      @{ Name = 'windows-powershell-5.1'; Command = (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'); Major = 5; Minor = 1 },
      @{ Name = 'powershell-7'; Command = 'C:\Program Files\PowerShell\7\pwsh.exe'; Major = 7; Minor = -1 }
  )
  foreach ($shell in $shells) {
      $command = Get-Command $shell.Command -ErrorAction Stop
      ...
      if ($LASTEXITCODE -ne 0 -or ([version]$version).Major -ne $shell.Major -or ...) { throw ('Required shell unavailable: ' + $shell.Name) }
  ```
  并额外处理了 5.1 的 stderr→`RemoteException` 陷阱
  （[run_matrix.ps1:22-31](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_matrix.ps1#L22-L31>)）。
- **故障注入探针本身是独立程序**（不是 hook 候选函数）：
  [atomic_commit_probe.ps1:1-2](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/atomic_commit_probe.ps1#L1-L2>) 注释直言：
  `# Public filesystem fault injection; never hooks a candidate function or inspects source.`

### 验证层

**(1) 文件身份 = 卷序列号 + 文件索引（`GetFileInformationByHandle`）**
[run_tests.ps1:117-196](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L117-L196>)：
```csharp
[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
private static extern SafeFileHandle CreateFile(...);
[DllImport("kernel32.dll", SetLastError = true)]
private static extern bool GetFileInformationByHandle(SafeFileHandle fileHandle, out ByHandleFileInformation information);
...
        ulong index = ((ulong)information.FileIndexHigh << 32) | information.FileIndexLow;
        return information.VolumeSerialNumber.ToString("X8") + ":" + index.ToString("X16");
```
配套断言（同文件、Agent 想偷懒就会被抓）：
- [run_tests.ps1:319](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L319>)
  `Assert-Equal $after.Identity $markedBefore.Identity 'The primary file was replaced instead of editing its stream.'`
- [run_tests.ps1:797](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L797>)
  `Assert-Equal (Get-FileSnapshot -Path $duplicateLinkA).Identity $duplicateLinkBefore.Identity 'Hard-link identity handling must not replace the file object.'`
- [run_tests.ps1:997](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L997>)
  `Assert-Equal $metadataAfter.Identity $metadataBefore.Identity 'The file object must not be rebuilt to clean it.'`
- [run_tests.ps1:777](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L777>)
  `Assert-Equal $identityRun[0].Status 'Failed' 'An AuditPath that is the same file object as an input must be rejected.'`
- [run_tests.ps1:964](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L964>)
  `Assert-Equal $prefixConflictRun[0].Status 'Failed' 'A prefixed input must still detect an audit target that is the same file object.'`

**(2) WhatIf 的"零副作用"是逐项证据，不是一句话**
[run_tests.ps1:457-466](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L457-L466>)：
```powershell
$previewRun = @(Invoke-CleanerWithOptions -Inputs $previewPath -WhatIf -AuditPath $previewAudit)
    Assert-Equal $previewRun[0].Status 'WouldRemove' 'WhatIf must report WouldRemove for a marked file.'
    Assert-Equal ((Get-NamedStreamText -Path $previewPath -StreamName 'Zone.Identifier').Trim()) 'ZoneId=3' 'WhatIf removed or changed the target stream.'
    Assert-Equal $after.Hash $previewBefore.Hash 'WhatIf changed the primary file.'
    Assert-True (-not (Test-Path -LiteralPath $previewAudit)) 'WhatIf created an audit file.'
```
混合输入场景（非法项仍须逐项 `Failed` 且不改动文件）
[run_tests.ps1:482-496](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L482-L496>)。

**(3) Atomic 提交中途失败的"真实句柄冲突"与逐文件还原**
[atomic_commit_probe.ps1:12-16](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/atomic_commit_probe.ps1#L12-L16>)：
```csharp
public static SafeFileHandle LockStream(string path) {
    var handle = CreateFileW(path, 0x80000000, 3, IntPtr.Zero, 3, 0, IntPtr.Zero);
    if (handle.IsInvalid) { int code=Marshal.GetLastWin32Error(); handle.Dispose(); throw new System.ComponentModel.Win32Exception(code); }
    return handle;
}
```
判据（[atomic_commit_probe.ps1:44-60](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/atomic_commit_probe.ps1#L44-L60>)）：
```powershell
# Reading/writing the second stream remains possible; deletion gets a sharing
# violation only when attempted. A safe early rejection is also acceptable.
$lock=[OutsideAdsObservation]::LockStream($second+':Zone.Identifier')
$observer=New-Object OutsideAdsObservation ($first+':Zone.Identifier')
try { $results=@(Invoke-CleanerWithOptions -Inputs @($first,$second) -Atomic) }
finally { $observer.Dispose(); $lock.Dispose() }
...
    $restored=$restored -and (([string](Get-NamedStreamText $file 'Zone.Identifier')).Trim() -eq 'ZoneId=3')
    $restored=$restored -and (([string](Get-NamedStreamText $file 'Keep')).Trim() -eq 'must-survive')
    $restored=$restored -and $after.Hash -eq $before[$i].Hash -and $after.Identity -eq $before[$i].Identity -and $after.Attributes -eq $before[$i].Attributes
    $restored=$restored -and $afterTime.CreationTimeUtc -eq $times[$i].CreationTimeUtc -and $afterTime.LastWriteTimeUtc -eq $times[$i].LastWriteTimeUtc
$valid=@($results).Count -eq 2 -and @($results | Where-Object { $_.Status -ne 'Failed' -or [string]::IsNullOrWhiteSpace([string]$_.Error) }).Count -eq 0 -and $restored
```
> 注意两点：① 观测到"确实被删过"（`mutation_observed`）与"安全地提前拒绝"都算可接受，但**两种情况下状态都必须还原**；
> ② 回滚后每一个输入都必须报 `Failed` 且带可读 `Error`（不允许"批量级一句话"糊过去，见 rubric
> [rubric.json:144](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/rubric.json#L144>) 的 `Confirms the outcome of a failed atomic rollback per file and names the files whose target stream could not be restored instead of hiding them behind a batch-level message.`）。

另一种共享模式探针用于"回滚报告"用例
（[stream_share_probe.ps1:19-28](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/stream_share_probe.ps1#L19-L28>)）：
```csharp
public static SafeFileHandle Lock(string path, uint share) {
    // GENERIC_READ with a caller-supplied share mode: sharing mode 3 allows reads and writes
    // but not deletion, sharing mode 5 allows reads and deletion but not writing back.
    SafeFileHandle handle = CreateFile(path, 0x80000000u, share, IntPtr.Zero, 3, 0, IntPtr.Zero);
```

**(4) 用拒绝写入的 ACL 制造"审计目标不可写"**
[run_tests.ps1:810](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L810>)、
[870](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/run_tests.ps1#L870>)：
`$denyUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name`（随后对该用户设 deny-write 规则）。
> 对应题面第 13 条：审计目标必须在**任何删除之前**确认可写。

**(5) rubric 维度（16 项）** 见
[rubric.json:6-166](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/002.6/tests/rubric.json#L6-L166>)，
其中第 118 行那条是身份判定的总纲：
> `Decides validity and audit-target conflicts from the real file identity and the whole parent chain, not from the leaf path string: a path reached through a reparse-point parent is rejected, and an AuditPath that is the same file object as an input (hard link, different spelling or case) fails before any deletion.`

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| 用 `Remove-Item` 删主文件再重建（或 `WriteAllBytes` 回写） | `Identity` 断言（319/797/997）+ 时间/属性/Hash 比对 |
| 用 `-Path` 字符串比较判断"审计路径是否等于输入" | 硬链接/大小写/`.\`/`\\?\` 四个变体用例（777/964） |
| 只检查叶节点是否 Reparse Point | 父链 Junction 用例（题面第 10 条 + 第 14 条组合用例） |
| 用 `-Stream` 名通配/不区分大小写地删（误删 `Zone.Identifier.bak`） | 其他流逐字节不变断言 |
| 原子模式"边删边报错" | `atomic_commit_probe.ps1` 的回滚还原 + 每项 `Failed` + `Error` |
| 只在 PowerShell 7 上跑通 | `run_matrix.ps1` 双宿主；5.1 上 `-Stream`/`ShouldProcess` 行为差异 |
| 先删后判断审计目标可写 | 第 13 条 deny-ACL 用例（810/870） |

强模型能过：契约写得极细（16 条），但每条都指向"必须用真实文件身份 / 真实流 / 真实共享语义"。

### 机制关键词

`Zone.Identifier`、ADS、`Get-Item -Stream`、`Set-Content -Stream`、`GetFileInformationByHandle`、
`VolumeSerialNumber` + `FileIndex`、`NumberOfLinks`、同文件对象身份（hard link / 大小写 / `.\` / `\\?\`）、
`ReparsePoint`/`Junction` 父链、`CreateFileW` share mode 3/5/7、`LockStream` 独占 ADS 句柄、
`WhatIf`/`ShouldProcess`、Atomic 回滚、deny-write ACL、Windows PowerShell 5.1 vs PowerShell 7 双宿主。

---

## 003 windows-file-share-classification-002：Win32 共享打开模式、原始错误码、低权隔离进程

### 题面层

> **原文**（[instruction.md:3](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/instruction.md#L3>)）
> ```
> 请修复工作区里的命令行程序，让它按 Windows 的实际打开结果返回状态。程序从标准输入读一个 JSON 对象，向标准输出写一个 JSON 对象，在 Windows Server 2022/.NET Framework 上运行；不要修改 `build.ps1`。
> ```
> **解释**：一句话把运行平台与判据来源钉死——"按 Windows 的**实际打开结果**"。

> **原文**（[instruction.md:6](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/instruction.md#L6>)）
> ```
> R2：打开失败时，`win32` 必须是 Windows 返回的原始错误码。错误 32 返回 `SharingViolation`，错误 33 返回 `LockViolation`，错误 2 或 3 返回 `NotFound`，其他错误返回 `Error`。例如，文件或父目录不存在时返回 `NotFound`。
> ```
> **解释**：判据是**内核返回的错误码**，不是自定义枚举或字符串近似。

> **原文**（[instruction.md:7](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/instruction.md#L7>)）
> ```
> R3：`allowRead`、`allowWrite` 和 `allowDelete` 各自生效；某一项为 false 时，若已有句柄正在按该项访问文件，新打开请求会因共享冲突失败。不能先换一组共享设置试开，再根据请求伪造结果。
> ```
> **解释**：明文禁止"先试开再伪造"——即禁止用启发式猜答案。

> **原文**（[instruction.md:8](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/instruction.md#L8>)）
> ```
> R4：请求还可以带 `probeRange`……有效范围要检查能否临时独占锁定后立即释放，不读写文件内容。若其他进程已锁住与之重叠的字节范围，返回 `LockViolation` 和错误码 33；若未冲突，仍返回 `Opened` 和错误码 0。
> ```
> **解释**：要求真实 `LockFileEx`/`UnlockFileEx` 语义，且带"临时锁定后立即释放"的副作用约束。

- **是否点名具体 Windows 对象/机制**：是（Win32 共享模式、原始错误码 32/33/2/3/87、字节范围锁）。
- **是否声明"不需要其他操作系统版本"**：**没有**；反而把 OS build、Framework 与 x64 编译器列为环境硬门槛。

### 环境层

- **Windows build / x64 / Framework 编译器三重门槛**
  （[validate_environment.ps1:2-5](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/environment/validate_environment.ps1#L2-L5>)）：
  ```powershell
  if ([Environment]::OSVersion.Version.Build -ne 20348) { throw 'Windows Server 2022 build 20348 required' }
  if (-not [Environment]::Is64BitOperatingSystem) { throw 'x64 Windows required' }
  $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
  if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework compiler missing' }
  ```
- 镜像把"不能用等价运行时替代"写在注释里
  （[Dockerfile:1-4](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/environment/Dockerfile#L1-L4>)）：
  ```dockerfile
  # This local task requires the frozen Windows account adapter.
  # NanoServer is not an equivalent runtime for .NET Framework or these tests.
  # A receiver image digest must be supplied when the receiver chooses containers.
  FROM mcr.microsoft.com/windows/servercore@sha256:e10503b9...
  ```
- 平台声明（[adapter.toml:4-11](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/environment/adapter.toml#L4-L11>)）：
  `edition = "Windows Server 2022 Standard"`、`build = "20348"`、`shell = "Windows PowerShell 5.1"`、
  `framework = "NET Framework 4.x"`、`network = "blocked-per-local-user"`、`permissions = "standard-user; own workspace; assigned registry roots"`。
- **真实隔离账户 + 真实 ACL + 出站阻断 + 双视图注册表授权**
  （[sandbox.ps1:8-33](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/sandbox.ps1#L8-L33>)）：
  ```powershell
  $user = New-LocalUser -Name $data.user -Password $password -AccountNeverExpires -PasswordNeverExpires -Description 'Temporary Outside Harbor evaluation account'
  Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $user
  ...
  $acl = Get-Acl -LiteralPath $root
  $acl.SetAccessRuleProtection($true,$false)
  foreach ($principal in @('S-1-5-18','S-1-5-32-544',$sid)) { ... 'FullControl','ContainerInherit,ObjectInherit','None','Allow' ... }
  Set-Acl -LiteralPath $root -AclObject $acl
  New-NetFirewallRule -Name ('OHB-' + $data.user) ... -Direction Outbound -Action Block -Profile Any -LocalUser ('D:(A;;CC;;;' + $sid + ')')
  foreach ($view in @([Microsoft.Win32.RegistryView]::Registry32,[Microsoft.Win32.RegistryView]::Registry64)) { ... $security.AddAccessRule(...); $key.SetAccessControl($security) }
  ```
  清理阶段做**残留断言**（[sandbox.ps1:46-67](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/sandbox.ps1#L46-L67>)）：
  ```powershell
  if (Get-LocalUser -Name $data.user -ErrorAction SilentlyContinue) { throw 'Account residue' }
  if (Get-NetFirewallRule -Name ('OHB-' + $data.user) -ErrorAction SilentlyContinue) { throw 'Firewall residue' }
  ```
- **候选以低权用户、在 Job Object 里被真实启动**（`CreateProcessWithLogonW`）
  （[sandbox_base.py:107-127](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/sandbox_base.py#L107-L127>)）：
  ```python
  success=A.CreateProcessWithLogonW(self.user,'.',self.password,0,PS,ctypes.create_unicode_buffer(command),0x08000404,environment,str(self.root),ctypes.byref(si),ctypes.byref(pi))
  if not success:raise RuntimeError('Low-privilege process launch failed: WinError '+str(ctypes.get_last_error()))
  job=K.CreateJobObjectW(None,None)
  limits=Limits();limits.basic.flags=0x2000|0x100|0x10;limits.procMemory=1024*1024*1024;limits.basic.affinity=3
  ```
- **隔离性自检**：先用一个独立编译的小 exe 验证"低权、读宿主文件被拒、无 API key 环境变量"
  （[sandbox_base.py:86-100](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/sandbox_base.py#L86-L100>)）：
  ```python
  bool denied=false;try{File.ReadAllText((string)request["protected"]);}catch(UnauthorizedAccessException){denied=true;}
  Console.WriteLine(json.Serialize(new {status="Healthy",echo=request["echo"],admin=new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator),hostDenied=denied,noApiEnvironment=Environment.GetEnvironmentVariable("OPENAI_API_KEY")==null}))
  ...
  if health!=dict(status='Healthy',echo='中文 UTF-8 ✓',admin=False,hostDenied=True,noApiEnvironment=True):raise RuntimeError('Independent runner health/isolation check failed: '+str(health))
  ```
  > 这是"**环境自身也作为被测对象**"的思路：连评测通道的隔离性都要先自证，否则报 infrastructure 错误。

### 验证层

**(1) 用真实持有句柄决定期望值 —— 判据只能是内核的真实返回码**
[verify_task.py:170-182](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/verify_task.py#L170-L182>)：
```python
def assert_access_share_flag(s,p,holder_access,flag,allowed):
 ...
 k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
 k.CreateFileW.restype=W.HANDLE
 holder=k.CreateFileW(str(p),holder_access,7,None,3,0,None)
 assert holder!=ctypes.c_void_p(-1).value,'holder CreateFileW failed: '+str(ctypes.get_last_error())
 ...
 expected=('Opened',0) if allowed else ('SharingViolation',32)
 assert (r.get('status'),r.get('win32'))==expected,(expected,r)
```
调用点把三个 allow 位分别对应到 Win32 访问位
（[verify_task.py:119-124](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/verify_task.py#L119-L124>)）：
```python
 ck(s,'read-share-allowed',lambda:assert_access_share_flag(s,path,0x80000000,'allowRead',True),out)
 ck(s,'read-share-denied',lambda:assert_access_share_flag(s,path,0x80000000,'allowRead',False),out)
 ck(s,'write-share-allowed',lambda:assert_access_share_flag(s,path,0x40000000,'allowWrite',True),out)
 ck(s,'write-share-denied',lambda:assert_access_share_flag(s,path,0x40000000,'allowWrite',False),out)
 ck(s,'delete-share-allowed',lambda:assert_access_share_flag(s,path,0x00010000,'allowDelete',True),out)
 ck(s,'delete-share-denied',lambda:assert_access_share_flag(s,path,0x00010000,'allowDelete',False),out)
```
独占与兼容两种基准（[verify_task.py:184-192](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/verify_task.py#L184-L192>)）：
```python
def assert_share_open(s,p):
 ... x=h.CreateFileW(str(p),0x80000000,7,None,3,0,None);assert x!=ctypes.c_void_p(-1).value
def assert_share_conflict(s,p):
 ... x=h.CreateFileW(str(p),0x80000000,0,None,3,0,None)
 try:assert s.invoke({'path':str(p),'write':False,'allowRead':False,'allowWrite':False,'allowDelete':False}).get('status')=='SharingViolation'
```

**(2) 字节范围锁：真实 `LockFileEx` + 重叠/不重叠/非法范围三态**
[verify_task.py:129-168](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/verify_task.py#L129-L168>)：
```python
 k.LockFileEx.argtypes=[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,W.DWORD,ctypes.POINTER(NativeOverlapped)];k.LockFileEx.restype=W.BOOL
 k.UnlockFileEx.argtypes=[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,ctypes.POINTER(NativeOverlapped)];k.UnlockFileEx.restype=W.BOOL
 ...
 if not k.LockFileEx(h,3,0,length&0xffffffff,(length>>32)&0xffffffff,ctypes.byref(ov)):
  error=ctypes.get_last_error();k.CloseHandle(h);raise RuntimeError('fixture LockFileEx failed: '+str(error))
 ...
 r=probe_range(s,path,0,1);assert r=={'status':'LockViolation','win32':33},r
 ...
 r=probe_range(s,path,1,1);assert r=={'status':'Opened','win32':0},r
 ...
 r=probe_range(s,path,0,0);assert r=={'status':'Invalid','win32':87},r
```
> "重叠 → 33 / 不重叠 → 0 / 非法长度 → 87"三个数字，任何"猜"的实现都无法同时命中。

**(3) NotFound 与写模式**
[verify_task.py:194-195](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/verify_task.py#L194-L195>)：
```python
def assert_not_found(s):assert s.invoke({'path':str(s.root/'absent'),'write':False,'allowRead':False,'allowWrite':False,'allowDelete':False}).get('status')=='NotFound'
def assert_write(s,p):assert s.invoke({'path':str(p),'write':True,'allowRead':True,'allowWrite':True,'allowDelete':True}).get('status')=='Opened'
```

**(4) 候选失败与基础设施失败严格分离**
[verify_task.py:8-13](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/verify_task.py#L8-L13>)：
```python
def ck(s,i,fn,out):
 d=defs[i]; status='PASS'; evidence='Independent Windows state and public protocol observed'
 try: fn()
 except (AssertionError,KeyError,IndexError,ValueError,TypeError) as e: status='FAIL'; evidence=str(e)[:1000]
 except Exception as e: status='ERROR'; evidence=type(e).__name__+': '+str(e)[:1000]; out.append(evidence)
```
> `AssertionError` → 候选 FAIL；其他异常 → ERROR/INVALID。这个区分让"环境坏了"不会被误判成"模型不行"。

**(5) 判分入口**（[run_tests.ps1:1-3](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/003/tests/run_tests.ps1#L1-L3>)）：
```powershell
& $Python (Join-Path $PSScriptRoot 'verify_task.py') --task-root (Split-Path -Parent $PSScriptRoot) --workspace $WorkspaceRoot --output $OutputPath --run-id ([Guid]::NewGuid().ToString('N'))
```

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| 用 `File.Exists` / 托管异常类型推断状态 | `win32` 原始码断言（32/33/2/3/87） |
| "先按各种共享模式试开一遍，再按请求编结果" | 三个 allow 位 × 独占/兼容 × 字节锁组合（题面 R3 明文禁止；判据是真句柄） |
| 用 `FileStream` 默认共享模式（`ReadWrite`）糊过去 | `delete-share-*` 与 `read/write-share-denied` 用例 |
| 用文件长度判断 probeRange 合法性、不做真实加锁 | `byte-range-overlap` 必须 33、`byte-range-disjoint` 必须 0 |
| 在管理员/宿主账户下测试通过 | 评测在隔离低权账户 + Job Object 内运行（`CreateProcessWithLogonW`） |
| 忽略了父目录不存在 vs 文件不存在 | `not-found` / `missing-parent` 两条 |

### 机制关键词

`CreateFileW`、`FILE_SHARE_READ/WRITE/DELETE`（share=0/3/5/7）、`ERROR_SHARING_VIOLATION(32)`、
`ERROR_LOCK_VIOLATION(33)`、`ERROR_FILE_NOT_FOUND(2)`/`ERROR_PATH_NOT_FOUND(3)`、`ERROR_INVALID_PARAMETER(87)`、
`LockFileEx`/`UnlockFileEx` + `OVERLAPPED`、`CreateProcessWithLogonW`、Job Object、
`New-LocalUser`/`Set-Acl`/`New-NetFirewallRule`、`Registry32`/`Registry64` 双视图授权、Windows Server 2022 build 20348。

---

## 018 windows-named-event-003：跨进程命名 Event 与句柄生命周期

### 题面层

> **原文**（[instruction.md:1](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/instruction.md#L1>)）
> ```
> 请修复 workspace/candidate.ps1，参数为 -Name、-Action Wait|Signal、-TimeoutMs。使用当前登录会话的 Windows 命名事件：Signal 应创建或打开事件并置为 signaled，返回 Status="signaled"；Wait 在超时内收到信号返回 Status="signaled"，否则返回 Status="timeout"。必须释放句柄，不得终止其他进程，Name 不同的事件不能相互影响。
> ```
> **解释**：验收对象是**内核命名事件对象**（`CreateEvent`/`OpenEvent` 语义），并要求句柄释放与名字隔离。

> **原文**（[instruction.md:3](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/instruction.md#L3>)）
> ```
> 事件采用手动重置语义；Wait 不消费信号。测试及调用方会在需要跨进程共享期间持有该事件的句柄，事件寿命随最后一个句柄关闭而结束。TimeoutMs 为 0 到 5000 毫秒。
> ```
> **解释**：明确告知"**测试会持有该事件的句柄**"——把跨进程互认写成公开契约，候选不能再假设自己独占对象。

> **原文**（[instruction.md:5](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/instruction.md#L5>)）
> ```
> 真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS。只修改工作区 candidate.ps1，保持参数入口；离线运行，不输出额外日志。
> ```
> **解释**：环境冻结到具体 build 与 shell 版本。**没有任何"不需要其他操作系统版本"的措辞。**

- **是否点名具体 Windows 对象/机制**：是（"Windows 命名事件"、手动重置、跨进程句柄、会话命名空间）。
- **是否声明"不需要其他操作系统版本"**：**没有**；相反把 build 20348 + PS 7.5.10 列为硬条件。

### 环境层

- **非 Windows / 非该版本必然失败**
  （[validate_environment.ps1:1-3](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/environment/validate_environment.ps1#L1-L3>)）：
  ```powershell
  $ErrorActionPreference='Stop'
  if(!$IsWindows-or $PSVersionTable.PSVersion.ToString()-ne '7.5.10'){throw 'Frozen Windows PowerShell runtime required'}
  if((Get-CimInstance Win32_OperatingSystem).Version-ne '10.0.20348'){throw 'Frozen Windows build required'}
  ```
  > 注意是**精确等于** `7.5.10` 与 `10.0.20348`，不是"≥"。
- 镜像与平台声明：
  [task.toml:2](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/task.toml#L2>)
  `docker_image = "mcr.microsoft.com/powershell:7.5-windowsservercore-ltsc2022"`；
  [task.toml:18-27](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/task.toml#L18-L27>)
  声明 `edition/build/architecture/locale/shell/filesystem/network_mode`；
  [Dockerfile:1](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/environment/Dockerfile#L1>) 同镜像。
- prepare 先跑环境校验再建工作区
  （[prepare.ps1:3-6](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/environment/prepare.ps1#L3-L6>)）。

### 验证层

**全部 5 个用例都在"评测器自己持有内核对象句柄"的前提下断言**
（[run_tests.ps1:9-35](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/tests/run_tests.ps1#L9-L35>)）：

**(1) 同进程互认：候选 Signal 后，测试持有的同名事件必须变 signaled**
```powershell
try {$passed=& { $n='Local\Bench_'+[Guid]::NewGuid().ToString('N');$e=[Threading.EventWaitHandle]::new($false,'ManualReset',$n);try{$r=& $candidate -Name $n -Action Signal -TimeoutMs 0;($r.Status-eq 'signaled')-and($e.WaitOne(0))}finally{$e.Dispose()} };...}
```
> `$e.WaitOne(0)` 是灵魂：只有候选真的操作了**同一个内核对象**才可能为真。
> 用本地变量、文件、环境变量或进程内状态模拟的实现，永远无法让测试进程的句柄变信号。

**(2) 手动重置 + 不消费信号**（同文件 15 行）
```powershell
$e=[Threading.EventWaitHandle]::new($true,'ManualReset',$n);try{$r=& $candidate -Name $n -Action Wait -TimeoutMs 0;$r2=& $candidate -Name $n -Action Wait -TimeoutMs 0;($r.Status-eq 'signaled')-and($r2.Status-eq 'signaled')-and($e.WaitOne(0))}
```
> 连续两次 `Wait` 都必须 signaled，且测试句柄仍 signaled → 同时封死 AutoReset 语义与"消费信号"实现。

**(3) 真实跨进程：子进程 Signal，父进程观测**
```powershell
$child=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList @('-NoProfile','-File',('"'+$candidate+'"'),'-Name',$n,'-Action','Signal','-TimeoutMs','0') -PassThru -WindowStyle Hidden;
try{if(!$child.WaitForExit(15000)){throw 'Infrastructure: event child completion timeout'};$e.WaitOne(0)-and($child.ExitCode-eq 0)}finally{...$child.Kill($true)...}
```
> 跨进程才是命名事件的**唯一存在理由**；同进程内存 flag 在这里必然失败。

**(4) 超时与名字隔离**
```powershell
try {$passed=& { $n='Local\Bench_'+...;$r=& $candidate -Name $n -Action Wait -TimeoutMs 30;$r.Status-eq 'timeout'  };...}
...
try {$passed=& { $n='Local\Bench_'+...;$e=[Threading.EventWaitHandle]::new($true,'ManualReset',$n);try{$r=& $candidate -Name ($n+'_other') -Action Wait -TimeoutMs 0;($r.Status-eq 'timeout')-and($e.WaitOne(0))}finally{$e.Dispose()} };...}
```
> 最后一条同时验证"不同 Name 不串扰"和"不得误置位别的对象"。

**(5) 计分与 INVALID 分离**
（[run_tests.ps1:37-39](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/tests/run_tests.ps1#L37-L39>)）
```powershell
$invalid=@($results|Where-Object status -notin @('PASS','FAIL')).Count-gt 0;$validity=if($invalid){'INVALID'}else{'VALID'};$score=if($invalid){$null}else{[int](@($results|Where-Object status -ne 'PASS').Count-eq 0)}
...
if($invalid){exit 2}elseif($score-eq 1){exit 0}else{exit 1}
```
> 基础设施异常以 `Infrastructure:` 前缀标记（见各 `throw 'Infrastructure: ...'`），专门与候选行为失败区分。

> **模板复用观察（可作为"常见坑"）**：该脚本每个用例里都有
> `$reg='Software\OutsideHarborBench\'+[Guid]::NewGuid().ToString('N')` 与
> `finally {[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}`
> （如 [run_tests.ps1:7](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/tests/run_tests.ps1#L7>)、
> [run_tests.ps1:10](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/018/tests/run_tests.ps1#L10>)），
> 与本题（命名事件）毫无关系——这是从注册表类题模板复制来的残留代码。
> 说明这套"一题一机制"的框架是从同一族模板派生，复用时需清理无关残留。

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| 用进程内变量 / 文件 / 全局状态模拟"信号" | `native_signal` 的 `$e.WaitOne(0)` |
| 用 `AutoResetEvent` 或 `Set()` 后立刻 `Reset()` | `native_wait_persist` 的连续两次 Wait |
| 用匿名 event / `Local\` 之外的随意名 / 名字拼接不一致 | `other_name_unchanged` + 跨进程用例 |
| 不释放句柄（等待对象泄漏） | 题面第 1 条 + 用例间的对象寿命契约（事件寿命随最后一个句柄关闭结束） |
| 直接 `Stop-Process` 别的进程来"清场" | 题面明文禁止（评测器比对子进程退出码与自身句柄状态） |

### 机制关键词

`EventWaitHandle`（`ManualReset`）、`Local\` 会话命名空间、`CreateEvent`/`OpenEvent`、
`WaitForSingleObject`/`WaitOne(0)`、跨进程句柄共享、句柄生命周期、"最后一个句柄关闭则对象销毁"、
`Start-Process pwsh.exe` 子进程、Windows build 20348 / PowerShell 7.5.10 冻结。

---

## 020 windows-named-mutex-002：命名 Mutex 与 abandoned 语义

### 题面层

> **原文**（[instruction.md:1](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/instruction.md#L1>)）
> ```
> 请修复 workspace/candidate.ps1 的单实例入口，参数 -Name、-HoldMs、-TimeoutMs。Name 是同一登录会话里的 Windows 命名 mutex 名称，各进程使用完全相同的 Name。获得互斥锁后等待 HoldMs 毫秒，释放锁，返回 Status="entered"；在 TimeoutMs 内未获得锁则返回 Status="busy"。已有持锁进程退出留下 abandoned mutex 时，下一次调用仍应进入并正常释放。不同名字不能相互阻塞，不能终止其他进程。HoldMs 和 TimeoutMs 为 0 到 2000 的整数。调用结束不得残留自己持有的锁。
> ```
> **解释**：一句话里塞满 Windows 独有语义：命名 mutex、同一会话命名空间、**abandoned mutex**、
> 跨进程互斥、真实持有时长、不得残留持有。`abandoned`（持锁进程未释放就退出）只有内核 mutex 才有。

> **原文**（[instruction.md:3](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/instruction.md#L3>)）
> ```
> 运行环境是 Windows Server 2022 x64（20348）、PowerShell 7.5.10 和 NTFS，本题离线运行。只修改 workspace/candidate.ps1，保持上述参数入口，不输出额外日志。
> ```
> **解释**：同样把环境冻结到具体版本；**没有"不需要其他操作系统版本"的免责表述**。

- **是否点名具体 Windows 对象/机制**：是（命名 mutex、abandoned、会话命名空间、跨进程持有）。
- **是否声明"不需要其他操作系统版本"**：**没有**。

### 环境层

- 三重门槛（[validate_environment.ps1:2-5](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/environment/validate_environment.ps1#L2-L5>)）：
  ```powershell
  if(!$IsWindows){throw 'Windows required'}
  if($PSVersionTable.PSVersion -lt [version]'7.5'){throw 'PowerShell 7.5 required'}
  $os=Get-CimInstance Win32_OperatingSystem
  if($os.Version-ne '10.0.20348'){throw 'Windows Server 2022 build 20348 required'}
  ```
- 镜像与平台声明同 018（[task.toml:2](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/task.toml#L2>)、
  [task.toml:18-27](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/task.toml#L18-L27>)）；
  清理脚本还防误删卷根（[cleanup.ps1:2-3](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/environment/cleanup.ps1#L2-L3>)）。

### 验证层

（[run_tests.ps1:11-37](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/tests/run_tests.ps1#L11-L37>)）

**(1) 内核互认：候选释放后，测试进程必须能拿到同一把锁**
```powershell
try {$passed=& { $name='Local\Bench_'+[Guid]::NewGuid().ToString('N');$r=& $candidate -Name $name -HoldMs 20 -TimeoutMs 100;$m=[Threading.Mutex]::new($false,$name);try{$ok=$m.WaitOne(100);if($ok){$m.ReleaseMutex()};($r.Status-eq 'entered')-and $ok}finally{$m.Dispose()} };...
```
> 若候选用的是文件锁/线程锁/进程内 bool，测试进程这把同名 `Mutex` 依然空闲——`$ok` 会暴露它。

**(2) abandoned mutex：子进程"拿到锁后直接退出"**
```powershell
try {$passed=& { $name='Local\Bench_'+[Guid]::NewGuid().ToString('N');$m=[Threading.Mutex]::new($false,$name);$code='$m=[Threading.Mutex]::new($false,"'+$name+'");$null=$m.WaitOne();[Environment]::Exit(0)';$enc=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code));$p=Start-Process pwsh -ArgumentList @('-NoProfile','-EncodedCommand',$enc) -PassThru -WindowStyle Hidden;if(!$p.WaitForExit(10000)){Stop-Process -Id $p.Id -Force;throw 'Infrastructure: abandoned-mutex child timeout'};if($p.ExitCode-ne 0){throw 'Infrastructure: abandoned-mutex child exit code'};try{$r=& $candidate -Name $name -HoldMs 0 -TimeoutMs 100;$r.Status-eq 'entered'}finally{$m.Dispose()} };...
```
> 关键在 `[Environment]::Exit(0)`：它**不执行 finally、不释放 mutex**，从而在核里留下 `WAIT_ABANDONED` 状态。
> 候选必须捕获 `AbandonedMutexException` 并继续（.NET 会在 `WaitOne` 时抛出它）。
> 这是"只有 Windows 才有的状态"被做成判据的教科书例子。

**(3) 竞态治理：用 ready sentinel 文件确保持锁已建立**
```powershell
$j=Start-ThreadJob -ScriptBlock {param($name,$ready)$m=[Threading.Mutex]::new($false,$name);$null=$m.WaitOne();[IO.File]::WriteAllText($ready,'1');Start-Sleep -Milliseconds 500;$m.ReleaseMutex();$m.Dispose()} -ArgumentList $name,$ready;
$readyWatch=[Diagnostics.Stopwatch]::StartNew();while(!(Test-Path -LiteralPath $ready)){if($readyWatch.ElapsedMilliseconds-gt 5000-or $j.State-in @('Failed','Stopped','Completed')){$j|Remove-Job -Force;throw 'Infrastructure: lock-owner readiness sentinel failed'};Start-Sleep -Milliseconds 10};
```
> 这是**并发判据的稳定性工程**：不靠 `Start-Sleep` 猜时间，而是等待"锁已真的被持有"的显式信号，
> 保证 `busy` 断言不会因调度抖动 flaky（否则强模型也会随机挂）。

**(4) 真实持有时长与零超时行为**
```powershell
$watch=[Diagnostics.Stopwatch]::StartNew();$r=& $candidate -Name ($name+'_other') -HoldMs 100 -TimeoutMs 0;($r.Status-eq 'entered')-and($watch.ElapsedMilliseconds-ge 75)-and($watch.ElapsedMilliseconds-lt 1000)
...
$watch=[Diagnostics.Stopwatch]::StartNew();$r=& $candidate -Name $name -HoldMs 0 -TimeoutMs 0;($r.Status-eq 'busy')-and($watch.ElapsedMilliseconds-lt 400)
```
> "不同名字不阻塞"必须**真的持有 100ms**（≥75ms），而不是立刻返回 `entered`；
> `TimeoutMs=0` 必须立即 `busy` 且总耗时 < 400ms。

**(5) 计分**：同 018 的三态结构（INVALID/exit 2、全 PASS/exit 0、否则 exit 1），
见 [run_tests.ps1:39-42](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/020/tests/run_tests.ps1#L39-L42>)。

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| 用进程内标志 / 文件锁实现"单实例" | `enter_release` 的测试进程 `WaitOne(100)` |
| 拿到锁不 `ReleaseMutex`，或异常路径泄漏 | `different_names_hold` 的时长断言 + 后续用例互认 |
| 用 `WaitOne` 但不捕获 `AbandonedMutexException` | `abandoned_enter`（子进程 `[Environment]::Exit`） |
| `TimeoutMs=0` 时仍长时间阻塞 | `busy_zero_timeout`（<400ms） |
| 不真正持有 `HoldMs`（直接返回 entered） | `different_names_hold`（≥75ms） |
| 为了"清理"而杀掉别的进程 | 题面禁止；评测器用线程任务持有锁并检查退出状态 |

### 机制关键词

`System.Threading.Mutex`、`Local\` 会话命名、`WAIT_ABANDONED` / `AbandonedMutexException`、
`Mutex.WaitOne(timeout)` / `ReleaseMutex`、`Start-Process -EncodedCommand`、
`[Environment]::Exit(0)`（绕过 finally，制造 abandoned）、`Start-ThreadJob` 持锁、
ready-sentinel 竞态治理、`Diagnostics.Stopwatch` 时长量测、Windows build 20348。

---

## 040 windows-subprocess-reader-error-005：Windows 线程式管道读取器的异常传播

### 题面层

> **原文**（[instruction.md:5](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/instruction.md#L5>)）
> ```
> 这个工作区包含一份来自 CPython 3.12 分支的 `Lib/subprocess.py`。在 Windows 上，当 `Popen.communicate()` 为多个管道或带超时时使用后台读取线程时，子进程输出的字节如果不能按调用方指定的编码解码，异常可能只停留在线程里，调用方拿到 `None` 或空结果。
> ```
> **解释**：题目背景本身就描述 Windows 的实现特征——**用后台线程读管道**（POSIX 用 `selectors`）。
> 这是平台差异被直接做成题目场景。

> **原文**（[instruction.md:13](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/instruction.md#L13>)）
> ```
> 1. **异常从调用方可见。** `Popen(..., stdout=PIPE, stderr=PIPE, encoding="utf-8").communicate()` 遇到不能解码的 stdout 或 stderr 时，必须在调用 `communicate()` 的线程中抛出原始 `UnicodeDecodeError`，异常的 `encoding`、原始字节对象、起止位置和原因保持准确。
> ```
> **解释**：验收点精确到异常的**五个属性**（encoding/object/start/end/reason），这意味着必须保留原始异常对象，
> 不能重新构造一个"差不多"的异常。

> **原文**（[instruction.md:14](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/instruction.md#L14>)）
> ```
> 2. **覆盖真实的 Windows 读取路径。** stdout、stderr、`STDOUT` 合并管道、设置 `timeout`、同时存在两条管道，以及一条输出正常而另一条输出非法的场景都必须遵守同一契约。子进程应能正常结束，读取管道和读取线程不得遗留。
> ```
> **解释**：把"Windows 读取路径"（线程 + 匿名管道）与"无线程/句柄泄漏"一起列为判据。

> **原文**（[instruction.md:22](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/instruction.md#L22>)）
> ```
> - 运行环境为 固定 Windows Server Core 2004 容器（amd64、zh-CN）、Python 3.12.14、PowerShell 7.6.5；质检主机为 Windows 10 Pro build 19045；测试以真实 Windows 子进程和匿名管道执行，不使用 WSL 或 Linux mock。
> ```
> **解释**：明文写"**不使用 WSL 或 Linux mock**"——直接堵死平台替代路径。这是 8 题中唯一显式提到
> "不用别的平台替代"的表述，且方向是**收紧到 Windows**。

> **原文**（[instruction.md:38](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/instruction.md#L38>) 与
> [instruction.md:42](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/instruction.md#L42>)）
> ```
> - stdout 与 stderr 同时发生不同的解码异常时，必须按两个 reader 线程实际完成读取并记录异常的先后顺序，把最先完成的原始异常交给调用线程；不能按固定的 stdout/stderr 优先级决定，也不得产生 reader thread 未处理异常。
> ...
> - 不能通过固定等待、重启子进程、源码字符串判断或修改测试来通过加强用例。
> ```
> **解释**：把"**真实完成顺序**"做成判据（而不是固定优先级），并显式禁止作弊手段。

- **是否点名具体 Windows 对象/机制**：是（Windows 上的后台读取线程、匿名管道、线程异常归属、进程/句柄残留）。
- **是否声明"不需要其他操作系统版本"**：**没有**；相反声明"不使用 WSL 或 Linux mock"。

### 环境层

- **真实 Windows Server Core 2004 基础镜像 + 自带 Python 3.12.14**
  （[Dockerfile:2-6](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/environment/Dockerfile#L2-L6>)）：
  ```dockerfile
  FROM mcr.microsoft.com/windows/servercore:2004@sha256:1241480fc719b88dbe0f482806d4f67ab90e10752ddd56c014f9a801d3aac991
  USER ContainerAdministrator
  SHELL ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]
  COPY toolchain/python-3.12.14-stdlib.zip C:/runtime/python.zip
  RUN $ErrorActionPreference='Stop'; Expand-Archive C:/runtime/python.zip C:/Python; Remove-Item C:/runtime/python.zip
  ```
- **测试目录与日志目录用 ACL 锁死（防改测试）**
  （[Dockerfile:16-19](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/environment/Dockerfile#L16-L19>)）：
  ```dockerfile
  & icacls.exe C:/task /grant '*S-1-5-93-2-2:(OI)(CI)M' /T | Out-Null; ...
  & icacls.exe C:/tests /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T | Out-Null; ...
  & icacls.exe C:/logs/verifier /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T | Out-Null; ...
  ```
  > `/inheritance:r` + 只给 SYSTEM/Administrators：Agent（ContainerUser）无法改测试与判分日志。
- **构建期就跑环境校验**（[Dockerfile:20](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/environment/Dockerfile#L20>)）；
  Agent/Verifier 以不同账户运行（[task.toml:23-27](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/task.toml#L23-L27>)：
  `user = "ContainerUser"` / `ContainerAdministrator`）。
- **三重预检**（[validate_environment.ps1:2-6](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/environment/validate_environment.ps1#L2-L6>)）：
  ```powershell
  if ($PSVersionTable.PSVersion.ToString() -ne '7.6.5') { throw 'PowerShell 7.6.5 is required' }
  if ($env:OS -ne 'Windows_NT' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Windows amd64 is required' }
  ...
  & $python -I -c 'import os,sys,struct,subprocess; assert os.name=="nt" and sys.version_info[:3]==(3,12,14) and struct.calcsize("P")==8; p=subprocess.run([sys.executable,"-I","-c","print(123)"],capture_output=True,timeout=5); assert p.returncode==0 and p.stdout.strip()==b"123"; print(sys.version)'
  if ($LASTEXITCODE -ne 0) { throw 'Python/child health preflight failed' }
  ```
  > 最后一行**在 Windows 上真实起一个子进程并读管道**——这正是本题被判据依赖的能力，
  > 预检不通过就判 INVALID，而不是让模型背锅。

### 验证层

**(1) 异常五元组用独立 oracle 比对**
（[run_tests.py:49-62](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L49-L62>)）：
```python
def expected_error(call, raw, encoding='utf-8'):
    try:
        raw.decode(encoding)
    except UnicodeDecodeError as oracle:
        expected = (oracle.encoding, oracle.object, oracle.start, oracle.end, oracle.reason)
    else:
        raise RuntimeError('invalid verifier fixture')
    try:
        call()
    except UnicodeDecodeError as actual:
        require((actual.encoding, actual.object, actual.start, actual.end, actual.reason) == expected,
                'decode exception does not retain its original attributes')
    else:
        raise AssertionError('caller did not receive UnicodeDecodeError')
```
> 判据不是"抛没抛异常"，而是**异常对象是否与真实解码失败逐字段一致**——伪造/包装过的异常会被逐字段比对抓住。

**(2) 顺序敏感：由 reader 完成顺序决定抛哪个异常（镜像双向用例）**
（[run_tests.py:273-286](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L273-L286>)、
[308-319](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L308-L319>)）：
```python
elif identifier == 'completion-order-error':
    # stderr reaches EOF first; the first completed reader error must win.
    code = ("import os,time;os.write(2,b'err:'+bytes([254])+b'\\n');os.close(2);"
            "time.sleep(0.35);os.write(1,b'out:'+bytes([255])+b'\\n')")
    p = popen(command(code), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
    try:
        p.communicate(timeout=5)
    except UnicodeDecodeError as exc:
        require(exc.object == b'err:' + bytes([254]) + b'\n',
                'decode error priority must follow reader completion order')
...
elif identifier == 'completion-order-reversed':
    # stdout completes first in this mirror fixture, so stdout must be selected.
```
> 两个镜像用例互为对照：任何"固定按 stdout 优先"或"固定按 stderr 优先"的实现在这两条里必然错一条。
> 这是**真正把并发完成顺序做成判据**的样板。

**(3) timeout 后重入：已读数据不重复、异常仍须传播、管道最终关闭**
（[run_tests.py:287-307](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L287-L307>)）：
```python
    try:
        p.communicate(timeout=0.1)
    except s.TimeoutExpired:
        pass
    else:
        raise AssertionError('timeout fixture unexpectedly completed')
    require(not p.stdout.closed, 'timeout closed unfinished stdout pipe')
    try:
        p.communicate(timeout=5)
    except UnicodeDecodeError as exc:
        require(exc.object == b'err:' + bytes([254]) + b'\n',
                'timeout retry did not preserve first completed reader error')
```
配合 `repeat-valid`（[266-272](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L266-L272>)）验证第二次 `communicate()` 返回同一结果。

**(4) 用真实命名事件门控 EOF —— 让"超时/重试"可确定复现**
（[run_tests.py:64-99](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L64-L99>)）：
```python
class Event:
    """A real named Win32 event gates EOF for deterministic timeout/retry tests."""
    def __init__(self):
        self.name = 'Local\\harbor-pipe-' + uuid.uuid4().hex
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        ...
        self.handle = self.api.CreateEventW(None, True, False, self.name)
```
```python
def gated_writer(event, stdout, stderr):
    code = f'''import ctypes,os
k=ctypes.WinDLL('kernel32',use_last_error=True)
...
h=k.OpenEventW(0x100000,False,{event.name!r})
...
os.write(1,{stdout!r})
os.write(2,{stderr!r})
r=k.WaitForSingleObject(h,10000)
```
> 子进程写完数据后**阻塞在命名事件上**，从而"何时 EOF"由评测器控制。
> 这是把 **Windows 内核同步对象**用作测试夹具的典范（避免 `sleep` 造成的 flaky）。

**(5) reader 线程异常归属与残留检测**
（[run_tests.py:104-106](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L104-L106>)、
[374-375](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L374-L375>)）：
```python
    old_hook = threading.excepthook
    threading.excepthook = lambda args: unhandled.append(type(args.exc_value).__name__)
    before_threads = {id(t) for t in threading.enumerate()}
...
        require(not unhandled, 'unhandled reader thread exception: '+repr(unhandled))
        require(not [t.name for t in threading.enumerate() if id(t) not in before_threads], 'new reader thread survived completion')
```
> 这两条把"异常只停留在 reader 线程里"这个**结构性缺陷**变成可观测判据：
> 只要异常逃脱到 `threading.excepthook`，或读取线程没退干净，就失败。

**(6) `BaseException`（含 `close()` 抛出）也必须由调用线程收到且关好管道**
（[run_tests.py:322-345](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L322-L345>)）：
```python
        class CloseExploder:
            ...
            def close(self):
                self.calls += 1
                self.closed = True
                if not original.closed:
                    original.close()
                if self.calls == 1:
                    raise KeyboardInterrupt()
        p.stdout = CloseExploder()
        try:
            p.communicate(timeout=5)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError('BaseException from reader close was swallowed')
        require(p.stdout.closed and p.stderr.closed, 'close BaseException path left pipes open')
```
另有 `reader-baseexception`（[346-363](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L346-L363>)）覆盖 `read()` 抛出。

**(7) 兼容性回归与失败清理**
`utf-16-le`（[255-257](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L255-L257>)）、
`stdin-invalid`（[258-265](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L258-L265>)）、
`strict-errors`（[364-371](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L364-L371>)）；
每个用例结束统一释放事件、杀子进程、关流、还原 `excepthook`
（[run_tests.py:379-394](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/run_tests.py#L379-L394>)）。
34 个必过用例清单见
[required_testcases.json](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/040/tests/required_testcases.json#L1-L177>)。

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| 把异常写进 `sys.stderr` / 日志，`communicate` 返回 `None` | `expected_error` 五元组比对（根本没有异常对象） |
| 重新构造一个 `UnicodeDecodeError('utf-8', ...)` | 五元组逐字段比对（`object/start/end/reason` 对不上） |
| 固定优先抛 stdout 异常（或固定 stderr） | `completion-order-error` 与 `completion-order-reversed` 必错一条 |
| 只修 `read()` 路径，不管 `close()`/`BaseException` | `reader-close-baseexception`、`reader-baseexception` |
| 用 `threading.excepthook` 兜住异常（而不是交给调用线程） | `:374` 未处理异常断言 + 调用线程必须收到 |
| 超时后丢弃已读数据 / 重复输出 | `repeat-valid`、`completion-order-timeout-retry` 的 object 精确匹配 |
| 用固定 `sleep` 让时序"看起来对" | 顺序敏感用例用命名事件门控 + 双向镜像；题面亦明文禁止"固定等待" |

### 机制关键词

CPython Windows `_readerthread`、`threading.excepthook`、`UnicodeDecodeError` 五元组、
匿名管道（`_winapi.CreatePipe`）、`STDOUT` 合并管道、`communicate(timeout=)` 后重入、
`BaseException` + `close()` 路径、reader 线程残留检测、命名 Win32 Event 门控 EOF（`CreateEventW`/`OpenEventW`/`WaitForSingleObject`）、
`errors='strict'/'replace'/'ignore'`、`icacls /inheritance:r` 锁测试目录、Windows Server Core 2004 + Python 3.12.14。

---

## 043 windows-hkcu-env-expand-001：`REG_EXPAND_SZ` 与"未展开原文"

### 题面层

> **原文**（[instruction.md:1](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/instruction.md#L1>)）
> ```
> 我们要给应用启动器准备一套用户环境配置，但不能在测试时改掉用户真正的 Environment。请完成 candidate.ps1，参数 -ProfileSubKey 和 -ManifestPath。ProfileSubKey 是 HKCU 下 Software\OutsideHarborEnvProfiles\ 后面的独立应用配置键的完整相对路径，例如 Software\OutsideHarborEnvProfiles\App42；不得写真实 HKCU\Environment 或 HKLM。
> ```
> **解释**：题目落在 HKCU 注册表上，并显式划出"只允许写的命名空间"，让越界写入成为可判定失败。

> **原文**（[instruction.md:3](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/instruction.md#L3>)）
> ```
> 逐项存到ProfileSubKey：expand=true写REG_EXPAND_SZ，false写REG_SZ；value是原始文本，即使带%USERPROFILE%也不能提前展开。旧值即使是DWORD等其他类型，也要迁成清单要求的类型。变量名称大小写按注册表习惯比较，不能留下重复项；空值是合法数据。
> ```
> **解释**：直接规定**注册表原生类型**（`REG_EXPAND_SZ` vs `REG_SZ`）与"不得提前展开"，
> 并引入"类型迁移"和"值名大小写不敏感去重"这两条 Windows 注册表特有的语义。

> **原文**（[instruction.md:5](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/instruction.md#L5>)）
> ```
> 全部写完后从注册表读取原生kind和不展开的数据，并返回单个对象：Status="synced"、Written=清单项数、Error=""、Variables数组。数组按清单顺序，每项有Name、Kind（ExpandString或String）、RawValue，必须反映实际存储值。重复执行幂等，原来的其他值和子键（包括空子键）保持不变。
> ```
> **解释**：要求**回读注册表**来产生返回值（而不是回显输入），并把 Kind 限定为 `ExpandString`/`String`。
> 这直接反掉了"直接返回输入"的偷懒实现。

> **原文**（[instruction.md:7](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/instruction.md#L7>)）
> ```
> 先校验整个清单。version不是1、variables不是数组、字段类型错误、重复变量名（不区分大小写）或ProfileSubKey不在上述独立命名空间内，都返回Status="rejected"、Written=0、Variables=[]、非空Error。错误时不能留下前几项修改，也不能创建原本不存在的键。
> ```
> **解释**：校验失败必须**零副作用**（含不得凭空创建键）——这是注册表类题最容易偷懒的地方。

> **原文**（[instruction.md:9](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/instruction.md#L9>)）
> ```
> 本题离线运行于真实Windows Server2022 x64 build20348、PowerShell7.5.10。工程里的样例展示启动器环境配置原始文本，不需要广播WM_SETTINGCHANGE，也不改变当前进程环境。只修改candidate.ps1与实现模块，不改清单规避验收。
> ```
> **解释**：环境冻结；同时明确"不需要广播 `WM_SETTINGCHANGE`"——即界定了机制的边界，
> **避免把不可判定项塞进验收**（这与我方题目需要学的"边界声明"写法一致）。

- **是否点名具体 Windows 对象/机制**：是（HKCU、`REG_EXPAND_SZ`/`REG_SZ`、注册表值名大小写、值类型迁移）。
- **是否声明"不需要其他操作系统版本"**：**没有**；只声明不需要某个 Windows 通知机制（`WM_SETTINGCHANGE`）。

### 环境层

- 三重门槛（[validate_environment.ps1:1-2](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/environment/validate_environment.ps1#L1-L2>)）：
  ```powershell
  if(!$IsWindows-or $PSVersionTable.PSVersion-lt [version]'7.5'){throw 'Native Windows PS7.5 required'}
  if((Get-CimInstance Win32_OperatingSystem).Version-ne '10.0.20348'){throw 'Server2022 required'}
  ```
- 镜像与平台： [task.toml:2](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/task.toml#L2>)、
  [task.toml:18-27](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/task.toml#L18-L27>)。
- **机制探针：注册表能否"原生类型 + 未展开原文"roundtrip**
  （[run_tests.ps1:27](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L27>)）：
  ```powershell
  Infra {$probe='Software\OutsideHarborEnvProfiles\preflight-'+[guid]::NewGuid().ToString('N');try{$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($probe);try{$k.SetValue('probe','%TEMP%\synthetic','ExpandString');if($k.GetValueKind('probe').ToString()-cne'ExpandString'-or$k.GetValue('probe',$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)-cne'%TEMP%\synthetic'){throw 'Registry cannot roundtrip native kind/raw'}}finally{$k.Dispose()}}finally{[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($probe,$false)}}
  ```
  > 这是本题的"非 Windows/非正常注册表必然失败"保障：探针失败会走 `Infra`，把结果标成 INVALID 而不是候选失败。

### 验证层

**(1) 原生 kind + 未展开原文的读取方式（判据的物理基础）**
（[run_tests.ps1:18](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L18>)）：
```powershell
function Native($name){Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{if(-not$k-or$k.GetValueNames()-inotcontains$name){return $null};[pscustomobject]@{Kind=$k.GetValueKind($name).ToString();Raw=$k.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}}finally{if($k){$k.Dispose()}}}}
```
> `DoNotExpandEnvironmentNames` 是关键：如果只用 `GetValue`，`REG_EXPAND_SZ` 会被展开，
> "未展开原文"就无从判定。

**(2) 候选返回值必须与注册表实际状态逐项一致（顺序也一致）**
（[run_tests.ps1:19](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L19>)）：
```powershell
function Synced($r,$vars){if($r.Status-cne'synced'-or$r.Written-ne$vars.Count-or$r.Error-cne''-or@($r.Variables).Count-ne$vars.Count){return $false};for($i=0;$i-lt$vars.Count;$i++){$native=Native $vars[$i].name;$x=$r.Variables[$i];if($null-eq$native-or$x.Name-cne$vars[$i].name-or$x.Kind-cne$native.Kind-or$x.RawValue-cne$native.Raw){return $false}};$true}
```
> 必须真的**回读注册表**：`Kind` 与 `RawValue` 都要与原生读值逐字符相等，且顺序一致。

**(3) 类型判定：`ExpandString` vs `String` 必须真区分**
（[run_tests.ps1:28](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L28>)）：
```powershell
Case native_kind_raw_and_report F2P {$a=Variable;$b=Variable 'LITERAL' '%TEMP%\literal' $false;$vars=@($a,$b);Save $vars;$r=Sync;$x=Native $a.name;$y=Native $b.name;(Synced $r $vars)-and$x.Kind-ceq'ExpandString'-and$x.Raw-ceq$a.value-and$y.Kind-ceq'String'-and$y.Raw-ceq$b.value}
```
其中 `Variable` 默认值含中文与 `%USERPROFILE%`
（[run_tests.ps1:17](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L17>)）：
```powershell
function Variable($name='CACHE_HOME',$value='%USERPROFILE%\中文 缓存',$expand=$true){[pscustomobject]@{name=$name;value=$value;expand=$expand}}
```
> 如果实现用会展开变量的 API 写值，`Raw` 就不再等于 `%USERPROFILE%\中文 缓存`，直接失败。

**(4) 类型迁移 + 大小写不敏感去重 + 空值合法**
（[run_tests.ps1:29](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L29>)）：
```powershell
Case migration_repeat_empty_value F2P {Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($reg);try{$k.SetValue('cache_home',17,'DWord')}finally{$k.Dispose()}};$vars=@((Variable 'CACHE_HOME' '' $false));Save $vars;$r=Sync;$q=Sync;$x=Native 'cache_home';$names=Infra {...@($k.GetValueNames())...};(Synced $r $vars)-and(Synced $q $vars)-and$x.Kind-ceq'String'-and$x.Raw-ceq''-and@($names).Count-eq1}
```
> 预置的 `cache_home` 是 **DWord 17**，必须被迁成 `String` 且值为空串，同时**值名只剩一个**
> （Windows 注册表值名大小写不敏感，`CACHE_HOME` 与 `cache_home` 是同一个值）。

**(5) 空清单不得创建键**
（[run_tests.ps1:30](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L30>)）：
```powershell
Case empty_manifest_no_key F2P {Save @();$r=Sync;$absent=Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{$null-eq$k}finally{if($k){$k.Dispose()}}};$r.Status-ceq'synced'-and$r.Written-eq0-and$r.Error-ceq''-and@($r.Variables).Count-eq0-and$absent}
```

**(6) "不许碰别的数据"用**全键树快照**逐字符比对**
（[run_tests.ps1:22-24](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L22-L24>)）：
```powershell
function Snapshot{Infra {
  function Walk($path){$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($path);try{if(-not$k){'M:'+ $path;return};'K:'+ $path;foreach($n in @($k.GetValueNames()|Sort-Object)){$v=$k.GetValue($n,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames);$raw=if($v-is[byte[]]){[Convert]::ToHexString($v)}else{ConvertTo-Json -InputObject $v -Compress};'V:'+$path+'|'+$n+'|'+$k.GetValueKind($n)+'|'+$raw};foreach($sub in @($k.GetSubKeyNames()|Sort-Object)){Walk ($path+'\'+$sub)}}finally{if($k){$k.Dispose()}}};@(Walk $reg)-join"`n"
}}
```
预置干扰数据（含 `REG_BINARY` 与空子键）后要求保持原样
（[run_tests.ps1:25](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L25>)）：
```powershell
function Seed{Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($reg);try{$k.SetValue('CACHE_HOME','before','String');$k.SetValue('Keep',[byte[]]@(7,0,255),'Binary');$k.CreateSubKey('empty child').Dispose();$sub=$k.CreateSubKey('nested');try{$sub.SetValue('old',42,'DWord')}finally{$sub.Dispose()}}finally{$k.Dispose()}}}
```
使用点（[run_tests.ps1:31](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L31>)、
[32](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L32>)、
[34](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L34>)）：
```powershell
Case unrelated_tree_preserved P2P {Seed;$keep=Native 'Keep';Save @(Variable);$null=Sync;$x=Native 'Keep';$sub=Infra {...OpenSubKey($reg+'\empty child')...};$x.Kind-ceq'Binary'-and[Convert]::ToHexString([byte[]]$x.Raw)-ceq'0700FF'-and$sub}
Case duplicate_input_no_change P2P {Seed;$before=Snapshot;Save @((Variable 'CACHE_HOME'),(Variable 'cache_home' 'new'));$r=Sync;(Reject $r)-and$before-ceq(Snapshot)}
Case invalid_manifest_no_partial_write P2P {Seed;$before=Snapshot;$a=Variable;$b=Variable 'SECOND';$b.expand='true';Save @($a,$b);$r=Sync;(Reject $r)-and$before-ceq(Snapshot)}
```
> `$before -ceq (Snapshot)` 是**整棵子树逐字符相等**（含值类型、二进制 hex、空子键路径），
> 比"检查某几个值没变"强得多。

**(7) 命名空间越界与九种非法清单**
（[run_tests.ps1:33](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L33>)）：
```powershell
Case invalid_namespace_no_real_environment_write P2P {Save @(Variable);$r=Call @{ProfileSubKey='Environment';ManifestPath=$manifest};Reject $r}
```
（[run_tests.ps1:35-41](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L35-L41>)）：
```powershell
  foreach ($n in @('','A=B',("A"+[char]0+"B"))){$variants.Add(@{version=1;variables=@($a,(Variable $n))})}
  foreach ($field in @('name','value','expand')){$b=Variable 'SECOND';$b.PSObject.Properties.Remove($field);$variants.Add(@{version=1;variables=@($a,$b)});$b=Variable 'SECOND';$b.$field=17;$variants.Add(@{version=1;variables=@($a,$b)})}
  $variants.Add(@{version=2;variables=@($a)});$variants.Add(@{version=1;variables=@{name='wrong-array'}});$ok=$true
  foreach($doc in $variants){...$r=Sync;$ok=$ok-and(Reject $r)-and$before-ceq(Snapshot)};$ok
```
> 每个非法清单都要求 `rejected` + 快照不变，覆盖 9 种输入形态。

**(8) 字面路径（中文 + 方括号）与夹具清理**
（[run_tests.ps1:9](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L9>)）：
```powershell
 $script:manifest=Join-Path $fixture '中文 [清单].json';$script:root=Join-Path $fixture '中文 [links]';$script:reg='Software\OutsideHarborEnvProfiles\'+[guid]::NewGuid().ToString('N')
```
每个用例 finally 都删键树与夹具目录（[run_tests.ps1:15](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L15>)），
并在结果里回报 `fixture_cleaned`
（[run_tests.ps1:48](<deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/043/tests/run_tests.ps1#L48>)）。

### 区分度设计

| 弱模型典型做法 | 被哪条判据稳定拦住 |
|---|---|
| 用 `Set-ItemProperty -Value '%USERPROFILE%\...'` 直接写（被展开/类型不对） | `Native` 的 `Kind` + `DoNotExpandEnvironmentNames` 读值比对 |
| 直接把输入清单回显成 `Variables` | `Synced` 要求 Kind/RawValue 与注册表一致（含顺序） |
| 用路径字符串 `SetValue('cache_home',...)` 不清旧值 | `migration_repeat_empty_value` 的 `@($names).Count -eq 1` |
| 失败前已经写了一部分 | `Snapshot` 前后整树逐字符相等（三条用例） |
| 顺手写真实 `HKCU\Environment` 或 `HKLM` | `invalid_namespace_no_real_environment_write` |
| 空清单时"顺手建键" | `empty_manifest_no_key`（`OpenSubKey` 必须为 null） |
| 用 `Remove-Item`/重建键的方式"同步" | `unrelated_tree_preserved` 的 Binary 字节与空子键断言 |

### 机制关键词

HKCU `Software\OutsideHarborEnvProfiles\<app>`、`REG_EXPAND_SZ`/`REG_SZ`、
`RegistryValueKind.ExpandString`/`String`、`RegistryValueOptions.DoNotExpandEnvironmentNames`、
`GetValueKind`、注册表值名大小写不敏感（`cache_home` ≡ `CACHE_HOME`）、旧类型（DWord）迁移、
空值合法、整键树快照（含空子键与二进制 hex）、中文/方括号字面路径、`WM_SETTINGCHANGE`（明确不做）。

---

## 可复用模板：给一道题注入"进程 / IPC / 注册表"类 Windows 机制依赖

以下清单从 8 题归纳，按"题面必写项 → 环境必做项 → 验证必做项 → 常见坑"组织，
可直接用于改造我方 wchunk-216 / wfmt-215 / wlogseg-218 这类"平台无关格式"题。

### A. 题面必写项（instruction.md）

1. **点名机制与对象**：写清要用哪个 Windows 对象/机制（注册表键与值类型、命名 Event/Mutex、
   文件共享模式、ADS、SACL、命名管道 reader 线程），而不是写"实现一个通知/清理/同步功能"。
2. **把"可观测验收"写成机制产生的差异**：例如"同值不同 registry kind 也算一次写入"
   （002.1:38）、"ACL 的显式/继承状态不能被权限掩码替代"（002.2:20）、"不能先试开再伪造结果"（003:7）。
3. **明确平台与版本冻结**：OS edition/build、shell 版本、Framework/Python 版本、文件系统（NTFS）、
   目标架构（x86/x64）。**不要写"不需要其他操作系统版本"**——要反过来把环境写成硬条件。
4. **为不可判定项划边界**：像 002.6:27（5.1 不支持长路径）、043:9（不需要广播 `WM_SETTINGCHANGE`）
   那样显式排除，避免"没有写明却被判分"。
5. **给出反作弊红线**：不得模拟、不得固定等待、不得按字符串判断、不得改测试
   （002.1:48 禁轮询；003:7 禁试开伪造；040:42 禁固定等待/源码字符串判断）。
6. **公开完整契约**：协议、CLI、记录形状、checkpoint 点、错误码映射都要在题面/契约文档里写全
   （002.2 的 `BATCH-CONTRACT.md`、002.1 的冻结契约注释）。难度应落在"必须真用机制"，而不是猜规格。

### B. 环境必做项（environment/）

1. **`validate_environment.ps1` 做机制探针，而不是只做 OS 判断**：
   - 注册表：在目标视图写入并读回 `REG_SZ`/`REG_QWORD`/`REG_EXPAND_SZ`（002.1:125-147、043:27）；
   - ADS：真造 `Zone.Identifier` 并读回，否则 `NTFS alternate data streams are unavailable.`（002.6:15-21）；
   - 子进程/管道：真实起一个子进程并读 stdout（040:5）；
   - 卷格式：`DriveInfo.DriveFormat -ne 'NTFS'` 即失败（002.2:7）。
2. **区分"环境不合格"与"候选失败"**：探针失败要让判分侧返回 `INVALID`/`null` 而不是 0 分
   （018:37-39、043:5 的 `Infra`、003:8-13 的 `ERROR`）。
3. **用真实 Windows 工具造夹具**：`fsutil sparse setflag`、`fsutil hardlink create`、`compact.exe /c`、
   `New-LocalUser` + `Set-Acl` + `New-NetFirewallRule`、`CreateProcessWithLogonW` + Job Object
   （002.2 provision、003 sandbox）。
4. **能力自检先于评分**：连评测通道的隔离性也自证（003 的 runner-health：`admin=false`、
   `hostDenied=true`、`noApiEnvironment=true`）。
5. **清理与残留断言**：清理注册表键树、账户、防火墙规则、夹具目录，并断言"确实没了"
   （003:63-64、002.1 cleanup 前后存在性、043 `fixture_cleaned`）。
6. **防作弊的基础设施**：测试目录 ACL 破继承、只给 SYSTEM/Administrators（040:17-18）；
   Agent 与 Verifier 用不同账户（040 task.toml）。
7. **工作区白名单**：拒绝在非预期路径下 prepare（002.2:4）。

### C. 验证必做项（tests/）

1. **评测器自己成为 Windows 对象持有者**（最重要）：
   - 自己创建同名 Event/Mutex 句柄，再看候选能否置位/释放（018:9、020:11）；
   - 自己用 `CreateFileW` + share mode 真持句柄，制造 `ERROR_SHARING_VIOLATION(32)`（003:170-182）；
   - 自己用 `LockFileEx` 真加字节范围锁，要求 `33`，不重叠要求 `0`（003:140-168）；
   - 自己独占 ADS 流句柄，让候选的删除必然拿到共享冲突（002.6 atomic_commit_probe:12-16,44-49）。
2. **身份/类型用系统提供的数值，而不是字符串近似**：
   - 文件身份：`GetFileInformationByHandle` → `VolumeSerialNumber:FileIndex`（002.6:117-196、002.2:81）；
   - 注册表类型：`GetValueKind` + `DoNotExpandEnvironmentNames`（043:18、002.2:644-646）；
   - ACL：ACE 二进制指纹 + 继承位分组 + `AreAccessRulesProtected`/`AreAuditRulesProtected`
     （002.2 candidate_contract:9-36、test_fail_to_pass:179-187）。
3. **留一个"控制组"把近似实现一票否决**：
   同值换 registry kind 也要回调（002.1:246-257）；镜像/反向场景各一条（040:273-319）；
   abandoned mutex（020:17）；`share=0` 独占（003:189-192）。
4. **把并发/跨进程做成显式判据 + 治理竞态**：
   第二个 OS 进程读取/发布（002.1 Program.cs:360、SystemStateChecks）；
   ready-sentinel 文件确保持锁已建立再断言 `busy`（020:23）；
   命名 Event 门控 EOF 取代 `sleep`（040:64-99）。
5. **资源与残留也判**：管道/句柄/线程必须关闭，`threading.enumerate()` 无新线程（040:374-375）、
   失败路径管道必须已关闭（040:117）、稀疏/压缩分配量上限（002.2:744-790）。
6. **真实崩溃恢复**：checkpoint 握手（候选写回执文件）+ 强制 `Kill()` + 新进程 recover 断言状态
   （002.2 test_batch:208-262,329-334）。
7. **异常对象要逐字段比对**：用独立 oracle 复现期望异常，比较五元组
   （040:49-62：`encoding/object/start/end/reason`）。
8. **全套判据挂 `rubric.json`/`required_testcases.json` 且聚合规则明确**：
   全过才 1 分，任一 FAIL 为 0，infra/error/missing 为 INVALID/null
   （018 rubric:29、003 rubric:5、043 rubric:61、002.1 rubric:4）。

### D. 常见坑

1. **"平台无关的机制代理"会被一眼看穿**：用文件/环境变量/进程内状态模拟命名 Event/Mutex 是无效实现
   （018/020 的判据专门抓这个）。若要涉及 IPC，必须落到内核命名对象。
2. **缺少机制探针**：只检查 `$IsWindows` 而不验证 ADS / 注册表原生类型 / 长路径 / 卷格式，
   会在受限宿主上把环境问题误判成模型失败。
3. **用 `sleep` 造并发场景 → flaky**：必须用显式握手（ready sentinel、命名事件、候选回执文件）
   来固定时序（020:23、040:64-99、002.2 test_batch:236）。
4. **只比"权限掩码/字符串/内容哈希"**：注册表要比 kind+raw，ACL 要比 ACE 二进制+继承位，
   文件要比身份+链接数+时间+属性+流——否则弱实现能蒙过。
5. **失败路径只报批量级错误**：原子回滚要求逐文件确认并点名未能还原的文件
   （002.6 rubric:144）。
6. **忘记清场与残留断言**：注册表键树、临时本地账户、防火墙规则、夹具文件都可能污染后续运行与判分
   （003:63-64、002.1 cleanup、002.6 `stream_share_probe` 句柄释放）。
7. **无关模板残留**：018/020 的 `run_tests.ps1` 里残留在 `HKCU\Software\OutsideHarborBench\...`
   建/删键的代码（018:7,10），与命名事件无关——从模板派生时必须清理，否则误导读者、也可能造成隐式耦合。
8. **版本漂移未锁死**：`-ne '7.5.10'` / `-ne '10.0.20348'` 这类精确比较比 `-lt` 更能保证
   "题库行为可复现"（018:2-3），但要与镜像标签保持同步，否则会在合法升级时误报 INVALID。
9. **把 Windows 限制写成"不需要 Windows"**：正确的写法是把平台限制列为**契约边界**
   （002.6:27 的长路径），而不是声明平台无关。

### E. 对我方三题的最小改造方向（据本批样本归纳）

| 我方题 | 现判据 | 建议注入的 Windows 机制锚点 |
|---|---|---|
| wchunk-216 | 平台无关容器格式/CRC | 改成"以注册表键值类型 + 值名大小写 + 键 last-write 时间为权威元数据"，并用跨进程写 + 键删除重建做判据 |
| wfmt-215 | 平台无关格式解析 | 改成"以 NTFS ADS/文件身份/属性（压缩/稀疏）+ `\\?\` 长路径"为保真对象，评测器用 `GetFileInformationByHandle` 与真实流句柄判定 |
| wlogseg-218 | 平台无关流式 IO | 改成"Windows 线程式管道读取的异常归属 + 超时重入 + 线程/句柄残留"，用命名 Event 门控 EOF、`threading.excepthook` 与线程残留做判据 |

> 共同要求：题面点名机制 → `validate_environment.ps1` 造真探针（失败即 INVALID）→
> 评测器自己持有 Windows 对象来观测候选，三者缺一不可。

