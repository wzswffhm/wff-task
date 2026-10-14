using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using Microsoft.Win32;

namespace LiteMonitor.src.Core
{
    /// <summary>
    /// 对 LiteMonitor 状态镜像注册表键的**变更通知**与**键元数据**访问。
    /// <para>背景：插件宿主与内置网页服务需要在状态镜像发生变化的**第一时间**刷新自己的缓存，</para>
    /// <para>现有实现用 200 毫秒一次的轮询反复打开注册表键比较内容，既费 CPU 又有最多 200 毫秒的延迟，</para>
    /// <para>现场要求改成基于系统注册表变更通知机制的事件驱动实现。</para>
    /// <para>实现只能依赖 net8.0-windows 自带的 BCL 与操作系统原生能力，**不得引入任何新的 NuGet 包**。</para>
    /// <para>本文档写明的每一条约定都是**可观测行为**，会被独立评测器在真实 Windows 上逐条验证；</para>
    /// <para>凡是本文档没有写明的行为，一律不作要求。</para>
    /// </summary>
    public static class RegistryNotify
    {
        /// <summary>
        /// 被监视的注册表子键（HKEY_CURRENT_USER，64 位视图）。
        /// <para>必须与 <see cref="StatusMirror.StatusSubKey"/> 保持一致，不得修改字面值。</para>
        /// </summary>
        public const string TargetSubKey = @"Software\LiteMonitor\Status";

        private const uint REG_NOTIFY_CHANGE_LAST_SET = 0x00000004;
        private const uint REG_NOTIFY_CHANGE_NAME = 0x00000001;
        private const int KEY_READ = 0x00020019;
        private const int KEY_NOTIFY = 0x00000010;
        private const int KEY_WOW64_64KEY = 0x00000100;
        private static readonly IntPtr HKCU = new IntPtr(unchecked((int)0x80000001));

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern int RegOpenKeyEx(IntPtr hKey, string lpSubKey, uint ulOptions, int samDesired, out IntPtr phkResult);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern int RegNotifyChangeKeyValue(IntPtr hKey,
            [MarshalAs(UnmanagedType.Bool)] bool bWatchSubtree, uint dwNotifyFilter, IntPtr hEvent,
            [MarshalAs(UnmanagedType.Bool)] bool fAsynchronous);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern int RegCloseKey(IntPtr hKey);

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern int RegQueryInfoKey(IntPtr hKey, StringBuilder? lpClass, ref int lpcbClass,
            IntPtr lpReserved, ref int lpcSubKeys, ref int lpcbMaxSubKeyLen, ref int lpcbMaxClassLen,
            ref int lpcValues, ref int lpcbMaxValueNameLen, ref int lpcbMaxValueLen,
            ref int lpcbSecurityDescriptor, out long lpftLastWriteTime);

        private static string ParentSubKey
        {
            get
            {
                int i = TargetSubKey.LastIndexOf('\\');
                return i > 0 ? TargetSubKey.Substring(0, i) : "";
            }
        }

        /// <summary>
        /// 开始监视 <see cref="TargetSubKey"/> 的**值变更**，每次变更调用一次 <paramref name="onChanged"/>。
        /// <para>约定：</para>
        /// <list type="number">
        /// <item><description>必须基于 Windows 的注册表变更通知机制，
        /// **不得用轮询**：不得周期性地打开该键去读取/比较它的值内容或最后写入时间来判断“有没有变化”；</description></item>
        /// <item><description>通知过滤器只包含「值条目变更」这一类（涵盖**新增值**、**覆盖已有值**、**删除值**三种情形），不得包含「子键增删/重命名」「安全描述符变更」「非安全属性变更」等其它类别；
        /// 因此**单纯地新建或删除一个子键**（不动任何值）**不应**触发回调；</description></item>
        /// <item><description><paramref name="watchSubtree"/> 为 <c>true</c> 时，<see cref="TargetSubKey"/> 之下**任意深度**子键里的值变更也必须触发回调，
        /// 同时 <see cref="TargetSubKey"/> 自身的值变更当然也要触发；
        /// 为 <c>false</c> 时只有 <see cref="TargetSubKey"/> 自身的值变更才触发，子键里的值变更**不得**触发；</description></item>
        /// <item><description>挂接监视这个动作本身**不得**立刻产生一次回调；只有在真正发生值变更之后才回调。</description></item>
        /// <item><description>时延：从另一个线程写入值的那一刻起，<paramref name="onChanged"/> 必须在 **200 毫秒内**被调用；
        /// 监视器空闲 5 秒以上之后的第一次变更，同样必须在 **200 毫秒内**回调；</description></item>
        /// <item><description>必须**自动重新挂接**：连续发生 N 次变更（每次间隔不小于 150 毫秒）时，必须收到不少于 N 次回调，
        /// 不得只在第一次变更时回调一次之后就永久静默；</description></item>
        /// <item><description>必须能承受**密集突发写入**：短时间连续写入几十次（回调可能被系统合并成少于写入次数）之后，
        /// 监视器**不得进入永久静默**，其后再发生的一次单独写入仍然必须在 **1 秒内**触发回调；</description></item>
        /// <item><description>开销：监视器处于空闲状态（期间没有任何注册表变更）时，连续 5 秒内**本进程的 CPU 时间增量必须小于 40 毫秒**；</description></item>
        /// <item><description>可以同时存在**多个**由 <see cref="Watch"/> 返回的监视句柄，它们彼此独立：
        /// 同一次值变更必须让每一个仍然存活的句柄各自的 <c>onChanged</c> 都被调用；
        /// 释放其中一个句柄**不得**影响其它句柄继续正常工作；</description></item>
        /// <item><description>释放掉一个句柄之后，再次调用 <see cref="Watch"/> 得到的新句柄必须照常工作；</description></item>
        /// <item><description>回调可能在任意线程上被调用；实现必须保证 <see cref="IDisposable.Dispose"/> 返回之后**不再**调用 <paramref name="onChanged"/>；</description></item>
        /// <item><description>如果 <paramref name="onChanged"/> 自己抛出异常，实现必须**吞掉**该异常（不得让异常逃逸到线程外部导致进程崩溃），
        /// 并且**继续正常监视**：其后发生的值变更仍然要照常触发回调；</description></item>
        /// <item><description>必须能从「目标键被删除后又被重新创建」这种情况中**自动恢复**：键重建之后再发生的值变更仍然要触发回调，
        /// 不得因为原先持有的键句柄已经指向被删除的旧键而永久静默；</description></item>
        /// <item><description>同样必须能从「目标键**连同它的上级键**整棵被删除之后又被重新创建出来」这种情况中**自动恢复**
        /// （产品的彻底清理/卸载就是这么做的：<see cref="StatusMirror.Purge"/> 删掉整棵根键，之后再次 <see cref="StatusMirror.Publish"/> 把镜像发布回来）：
        /// 重新发布之后再发生的值变更仍然要触发回调，不得因为上级键一时不存在、或原先持有的句柄已经全部失效就永久放弃监视；</description></item>
        /// <item><description><see cref="TargetSubKey"/> 不存在时必须返回 <c>null</c>，不得抛异常，也不得自行创建该键；</description></item>
        /// <item><description>返回的句柄的 <see cref="IDisposable.Dispose"/> 必须**幂等**（重复调用不抛异常、不产生额外副作用）、
        /// 必须在 **2 秒内**返回、不得抛异常；</description></item>
        /// <item><description>本方法在任何情况下都不得抛出异常，一切失败都以返回 <c>null</c> 表示。</description></item>
        /// </list>
        /// </summary>
        /// <returns>可用于停止监视的句柄；失败时返回 <c>null</c>。</returns>
        public static IDisposable? Watch(Action onChanged, bool watchSubtree)
        {
            if (onChanged == null) return null;
            try
            {
                IntPtr probe;
                if (!TryOpen(TargetSubKey, out probe)) return null;
                RegCloseKey(probe);
                return new Watcher(onChanged, watchSubtree);
            }
            catch
            {
                return null;
            }
        }

        /// <summary>
        /// 读取 <see cref="TargetSubKey"/> 的最后写入时间（由操作系统为该键记录的最后写入时间戳）。
        /// <para>约定：</para>
        /// <list type="number">
        /// <item><description>必须操作 HKEY_CURRENT_USER 的 **64 位注册表视图**；</description></item>
        /// <item><description>输出的 <see cref="DateTime"/> 的 <c>Kind</c> 必须恰好是 <see cref="DateTimeKind.Utc"/>；
        /// 该时间戳本身即为 **UTC** 时间，
        /// **不得**按本地时区解释，也不得再做任何本地时区换算；</description></item>
        /// <item><description>键存在且刚刚写入过值时，返回值必须为 <c>true</c>，且与 <see cref="DateTime.UtcNow"/> 之差的绝对值必须小于 120 秒；</description></item>
        /// <item><description>两次写入之间间隔不少于 1.4 秒时，第二次读到的时间必须**严格大于**第一次，
        /// 并且两次读数之差必须落在 **1.0 秒到 3.0 秒**这个区间内（用以确认时间刻度换算正确）；</description></item>
        /// <item><description><see cref="TargetSubKey"/> 不存在时必须返回 <c>false</c>，并把 <paramref name="lastWriteUtc"/> 置为 <c>default</c>，
        /// 不得抛异常，也不得自行创建该键；</description></item>
        /// <item><description>本方法在任何情况下都不得抛出异常。</description></item>
        /// </list>
        /// </summary>
        public static bool TryGetLastWriteTimeUtc(out DateTime lastWriteUtc)
        {
            lastWriteUtc = default;
            IntPtr hKey;
            if (!TryOpen(TargetSubKey, out hKey)) return false;
            try
            {
                int cbClass = 0, subKeys = 0, maxSubKeyLen = 0, maxClassLen = 0;
                int values = 0, maxValueNameLen = 0, maxValueLen = 0, sdLen = 0;
                long fileTime;
                int rc = RegQueryInfoKey(hKey, null, ref cbClass, IntPtr.Zero, ref subKeys, ref maxSubKeyLen,
                    ref maxClassLen, ref values, ref maxValueNameLen, ref maxValueLen, ref sdLen, out fileTime);
                if (rc != 0 || fileTime <= 0) return false;
                lastWriteUtc = DateTime.FromFileTimeUtc(fileTime);
                return true;
            }
            catch
            {
                return false;
            }
            finally
            {
                RegCloseKey(hKey);
            }
        }

        private static bool TryOpen(string sub, out IntPtr hKey)
        {
            hKey = IntPtr.Zero;
            if (string.IsNullOrEmpty(sub)) return false;
            try
            {
                int rc = RegOpenKeyEx(HKCU, sub, 0u, KEY_READ | KEY_NOTIFY | KEY_WOW64_64KEY, out hKey);
                return rc == 0 && hKey != IntPtr.Zero;
            }
            catch
            {
                hKey = IntPtr.Zero;
                return false;
            }
        }

        /// <summary>
        /// 事件驱动监视器。一条线程同时等待三类事件：
        /// (a) 目标键的值变更（LAST_SET）；
        /// (b) 父键的子键增删（NAME）——用来发现目标键被删除/重建，从而丢弃失效句柄重新打开；
        /// (c) 停止信号。
        /// 关键不变式：每一个事件在任意时刻**最多只有一个**挂起的通知请求，
        /// 因此不会出现重复请求相互覆盖/重复置位导致的丢事件或多余回调。
        /// </summary>
        private sealed class Watcher : IDisposable
        {
            private readonly Action _onChanged;
            private readonly bool _subtree;
            private readonly Thread _thread;
            private readonly ManualResetEvent _stop = new ManualResetEvent(false);
            private int _disposed;

            internal Watcher(Action onChanged, bool subtree)
            {
                _onChanged = onChanged;
                _subtree = subtree;
                _thread = new Thread(Loop);
                _thread.IsBackground = true;
                _thread.Name = "RegistryNotify.Watcher";
                _thread.Start();
            }

            private void Loop()
            {
                IntPtr hKey = IntPtr.Zero;
                IntPtr hParent = IntPtr.Zero;
                AutoResetEvent valueSignal = new AutoResetEvent(false);
                AutoResetEvent nameSignal = new AutoResetEvent(false);
                bool valueArmed = false;
                bool nameArmed = false;

                void ReleaseKey()
                {
                    if (hKey != IntPtr.Zero) { try { RegCloseKey(hKey); } catch { } hKey = IntPtr.Zero; }
                    valueArmed = false;
                    try { valueSignal.Reset(); } catch { }
                }

                void ReleaseParent()
                {
                    if (hParent != IntPtr.Zero) { try { RegCloseKey(hParent); } catch { } hParent = IntPtr.Zero; }
                    nameArmed = false;
                    try { nameSignal.Reset(); } catch { }
                }

                try
                {
                    while (!_stop.WaitOne(0))
                    {
                        try
                        {
                            if (hKey == IntPtr.Zero)
                            {
                                if (!TryOpen(TargetSubKey, out hKey)) { _stop.WaitOne(20); continue; }
                                valueArmed = false;
                            }
                            if (hParent == IntPtr.Zero)
                            {
                                if (!TryOpen(ParentSubKey, out hParent)) hParent = IntPtr.Zero;
                                nameArmed = false;
                            }

                            if (!valueArmed)
                            {
                                int rc = RegNotifyChangeKeyValue(hKey, _subtree, REG_NOTIFY_CHANGE_LAST_SET,
                                    valueSignal.SafeWaitHandle.DangerousGetHandle(), true);
                                if (rc != 0) { ReleaseKey(); _stop.WaitOne(20); continue; }
                                valueArmed = true;
                            }
                            if (hParent != IntPtr.Zero && !nameArmed)
                            {
                                int rcp = RegNotifyChangeKeyValue(hParent, false, REG_NOTIFY_CHANGE_NAME,
                                    nameSignal.SafeWaitHandle.DangerousGetHandle(), true);
                                nameArmed = rcp == 0;
                            }

                            int index = WaitHandle.WaitAny(new WaitHandle[] { valueSignal, nameSignal, _stop }, 400);
                            if (_stop.WaitOne(0)) return;

                            if (index == 0)
                            {
                                valueArmed = false;
                                int rc2 = RegNotifyChangeKeyValue(hKey, _subtree, REG_NOTIFY_CHANGE_LAST_SET,
                                    valueSignal.SafeWaitHandle.DangerousGetHandle(), true);
                                if (rc2 != 0) { ReleaseKey(); continue; }
                                valueArmed = true;
                                try { _onChanged(); } catch { }
                            }
                            else if (index == 1)
                            {
                                ReleaseKey();
                                ReleaseParent();
                            }
                            else if (!Alive(TargetSubKey))
                            {
                                ReleaseKey();
                                ReleaseParent();
                            }
                        }
                        catch
                        {
                            ReleaseKey();
                            ReleaseParent();
                        }
                    }
                }
                finally
                {
                    ReleaseKey();
                    ReleaseParent();
                    Thread.Sleep(5);
                    try { valueSignal.Dispose(); } catch { }
                    try { nameSignal.Dispose(); } catch { }
                }
            }

            private static bool Alive(string sub)
            {
                IntPtr probe;
                if (!TryOpen(sub, out probe)) return false;
                RegCloseKey(probe);
                return true;
            }

            public void Dispose()
            {
                if (Interlocked.Exchange(ref _disposed, 1) != 0) return;
                try { _stop.Set(); } catch { }
                try { _thread.Join(1500); } catch { }
                try { _stop.Dispose(); } catch { }
            }
        }
    }
}
