using System;
using System.Threading;
using Microsoft.Win32;

namespace LiteMonitor.src.Core
{
    /// <summary>
    /// LiteMonitor 最近一次运行状态的机器可读镜像。
    /// <para>用途：让插件宿主这类外部消费方在应用完整启动之前就能读到上次的运行状态，</para>
    /// <para>而不必解析体积较大、结构可变的 settings.json。</para>
    /// </summary>
    /// <param name="AutoStartEnabled">上次保存时“开机自启动”是否开启。</param>
    /// <param name="MonitorItemCount">上次保存时启用的监控项数量。</param>
    /// <param name="ThemeName">上次保存时的主题名称，允许包含非 ASCII（中文）字符。</param>
    /// <param name="TrafficUploadBytes">上次保存时的当日累计上传字节数，允许超过 <see cref="int.MaxValue"/>。</param>
    public readonly record struct StatusSnapshot(
        bool AutoStartEnabled,
        int MonitorItemCount,
        string ThemeName,
        long TrafficUploadBytes);

    /// <summary>
    /// 把 <see cref="StatusSnapshot"/> 发布到 HKEY_CURRENT_USER 下的状态镜像键，并让本进程内的订阅者及时知道“镜像变了”。
    /// <para>公开成员的名称、签名和常量值请保持不变。</para>
    /// </summary>
    public static class StatusMirror
    {
        /// <summary>本应用在 HKEY_CURRENT_USER 下占用的注册表根子键路径（64 位视图）。</summary>
        public const string RootSubKey = @"Software\LiteMonitor";

        /// <summary>运行状态镜像所在的注册表子键路径（位于 <see cref="RootSubKey"/> 之下）。</summary>
        public const string StatusSubKey = @"Software\LiteMonitor\Status";

        /// <summary>结构版本号值名，写入 <see cref="MirrorSchemaVersion"/>，读取时不匹配就整份镜像作废。</summary>
        public const string SchemaVersionValueName = "SchemaVersion";

        /// <summary>发布序号值名；每次 <see cref="Publish"/> 成功都会让它严格递增。</summary>
        public const string GenerationValueName = "Generation";

        /// <summary>“开机自启动”值名。</summary>
        public const string AutoStartValueName = "AutoStartEnabled";

        /// <summary>启用的监控项数量值名。</summary>
        public const string MonitorItemCountValueName = "MonitorItemCount";

        /// <summary>主题名称值名，允许包含非 ASCII（中文）字符。</summary>
        public const string ThemeNameValueName = "ThemeName";

        /// <summary>当日累计上传字节数值名，允许超过 <see cref="int.MaxValue"/>。</summary>
        public const string TrafficUploadBytesValueName = "TrafficUploadBytes";

        /// <summary>状态镜像的结构版本号，写入 <see cref="SchemaVersionValueName"/> 值。</summary>
        public const string MirrorSchemaVersion = "1";

        /// <summary>遗留轮询刷新器使用的轮询间隔（毫秒）。</summary>
        public const int LegacyPollIntervalMilliseconds = 200;

        /// <summary>
        /// 把快照写入 <see cref="StatusSubKey"/>，并把 <see cref="GenerationValueName"/> 严格递增。
        /// <para>约定：全部成功返回 <c>true</c>；键无法创建或任何值写不进去时返回 <c>false</c>；任何情况下都不抛异常。</para>
        /// <para>值类型固定为：<see cref="SchemaVersionValueName"/> = String，<see cref="GenerationValueName"/> = QWord，</para>
        /// <para><see cref="AutoStartValueName"/> = DWord（0/1），<see cref="MonitorItemCountValueName"/> = DWord，</para>
        /// <para><see cref="ThemeNameValueName"/> = String，<see cref="TrafficUploadBytesValueName"/> = QWord。</para>
        /// </summary>
        public static bool Publish(StatusSnapshot snapshot)
        {
            try
            {
                using RegistryKey baseKey = OpenBase();
                using RegistryKey? key = baseKey.CreateSubKey(StatusSubKey, writable: true);
                if (key is null) return false;

                long generation = ReadGenerationCore(key) + 1;
                if (generation < 1) generation = 1;

                key.SetValue(SchemaVersionValueName, MirrorSchemaVersion, RegistryValueKind.String);
                key.SetValue(AutoStartValueName, snapshot.AutoStartEnabled ? 1 : 0, RegistryValueKind.DWord);
                key.SetValue(MonitorItemCountValueName, snapshot.MonitorItemCount, RegistryValueKind.DWord);
                key.SetValue(ThemeNameValueName, snapshot.ThemeName ?? string.Empty, RegistryValueKind.String);
                key.SetValue(TrafficUploadBytesValueName, snapshot.TrafficUploadBytes, RegistryValueKind.QWord);
                key.SetValue(GenerationValueName, generation, RegistryValueKind.QWord);
                key.Flush();
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// 读回镜像。<see cref="SchemaVersionValueName"/> 缺失或不等于 <see cref="MirrorSchemaVersion"/> 时整份镜像作废：
        /// 返回 <c>false</c> 且 <paramref name="snapshot"/> 为 <c>default</c>。单个字段缺失或类型不对时该字段取默认值，其余字段照常返回。
        /// </summary>
        public static bool TryRead(out StatusSnapshot snapshot)
        {
            snapshot = default;
            try
            {
                using RegistryKey baseKey = OpenBase();
                using RegistryKey? key = baseKey.OpenSubKey(StatusSubKey, writable: false);
                if (key is null) return false;

                if (key.GetValue(SchemaVersionValueName) as string != MirrorSchemaVersion) return false;

                snapshot = new StatusSnapshot(
                    ToInt32(key.GetValue(AutoStartValueName)) != 0,
                    ToInt32(key.GetValue(MonitorItemCountValueName)),
                    key.GetValue(ThemeNameValueName) as string ?? string.Empty,
                    ToInt64(key.GetValue(TrafficUploadBytesValueName)));
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>读取当前发布序号；键或值不存在时返回 <c>-1</c>，任何情况下都不抛异常。</summary>
        public static long ReadGeneration()
        {
            try
            {
                using RegistryKey baseKey = OpenBase();
                using RegistryKey? key = baseKey.OpenSubKey(StatusSubKey, writable: false);
                if (key is null) return -1;
                return ReadGenerationCore(key);
            }
            catch
            {
                return -1;
            }
        }

        /// <summary>删除 <see cref="RootSubKey"/> 整棵键树（彻底卸载时调用）。幂等，任何情况下都不抛异常。</summary>
        public static void Purge()
        {
            try
            {
                using RegistryKey baseKey = OpenBase();
                baseKey.DeleteSubKeyTree(RootSubKey, throwOnMissingSubKey: false);
            }
            catch
            {
            }
        }

        /// <summary>
        /// 订阅“状态镜像发生了变化”，返回可用于退订的句柄。
        /// <para>**本轮迭代要求（公开签名冻结；当前实现是不合规的遗留轮询版，必须按下面的约定重写）**：</para>
        /// <list type="number">
        /// <item><description>必须改成**事件驱动**：内部只能借助 <see cref="RegistryNotify.Watch"/> 挂接系统的注册表变更通知，
        /// **不得**再使用任何周期性定时器去反复读取 <see cref="GenerationValueName"/> 做比较；</description></item>
        /// <item><description>触发条件是「<see cref="StatusSubKey"/> 自身发生了任意一次值写入」，
        /// 而**不是**「<see cref="GenerationValueName"/> 的数值变了」：写入 <see cref="ThemeNameValueName"/> 等其它值要触发，
        /// 把 <see cref="GenerationValueName"/> 重写成与原来完全相同的数值也要触发；</description></item>
        /// <item><description>只监视 <see cref="StatusSubKey"/> 自身，不监视它的子键（即以 <c>watchSubtree = false</c> 的语义挂接）：
        /// 子键里的值写入**不得**触发本订阅的回调；</description></item>
        /// <item><description>时延：从写入发生的那一刻起 <paramref name="onChanged"/> 必须在 **200 毫秒内**被调用；</description></item>
        /// <item><description>必须能承受连续多次写入：连续三次改写镜像值，三次都要收到回调，且期间 <see cref="GenerationValueName"/> 的数值保持不变；</description></item>
        /// <item><description>必须能活过一次完整的 <see cref="Purge"/> + <see cref="Publish"/> 循环（整棵 HKCU 镜像树被删掉又重建）：
        /// 重建之后再改写镜像值仍然要能收到回调；</description></item>
        /// <item><description><see cref="StatusSubKey"/> 不存在时返回 <c>null</c>，不得抛异常，也不得自行创建该键；</description></item>
        /// <item><description>返回句柄的 <see cref="IDisposable.Dispose"/> 必须幂等、必须在 **2 秒内**返回、之后不得再调用 <paramref name="onChanged"/>；</description></item>
        /// <item><description>本方法在任何情况下都不得抛出异常。</description></item>
        /// </list>
        /// </summary>
        /// <param name="onChanged">镜像发生变化时被调用的回调，可能在任意线程上被调用。</param>
        /// <returns>可用于退订的句柄；<see cref="StatusSubKey"/> 不存在或挂接失败时返回 <c>null</c>。</returns>
        public static IDisposable? StartRefresher(Action onChanged)
        {
            if (onChanged is null) return null;
            try
            {
                using RegistryKey baseKey = OpenBase();
                using RegistryKey? probe = baseKey.OpenSubKey(StatusSubKey, writable: false);
                if (probe is null) return null;
            }
            catch
            {
                return null;
            }

            return RegistryNotify.Watch(onChanged, false);
        }

        private static RegistryKey OpenBase() =>
            RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry64);

        private static long ReadGenerationCore(RegistryKey key)
        {
            object? raw = key.GetValue(GenerationValueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
            return ToInt64(raw);
        }

        private static long ToInt64(object? raw) => raw switch
        {
            long value => value,
            int value => value,
            uint value => value,
            _ => -1L,
        };

        private static int ToInt32(object? raw) => raw switch
        {
            int value => value,
            long value => (int)value,
            uint value => (int)value,
            _ => 0,
        };

    }
}
