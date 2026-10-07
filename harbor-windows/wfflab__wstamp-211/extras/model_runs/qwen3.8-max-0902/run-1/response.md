修复了 wstamp 包的时间戳/属性同步缺陷（issue #211），只改动了 wstamp/ 下 4 个实现文件，未触碰 tests/。全部行为在真实 Windows/NTFS 沙箱（且该卷 atime 更新为启用状态，最苛刻场景）上用 74 项验收自检逐条验证通过，3 个可见冒烟测试也通过。

**wstamp/stamps.py**
- `stamp_file(path, mtime_ns)`：改为 `os.utime(path, ns=(原atime_ns, mtime_ns))`——纳秒级精确设置 mtime（NTFS 100ns 粒度可逐纳秒往返），且保持 atime 原值（原实现把 atime 也覆盖成 mtime）。目标带只读属性时先检查、不做任何写动作，直接抛 `WStampError(kind="readonly")`（否则会撞上 WinError 5）。
- `snapshot_times` 语义不变（mtime_ns/atime_ns/created=st_ctime，符合 Windows birth time 契约）。

**wstamp/attributes.py**
- 修复 `GetFileAttributesW` 的 ctypes 原型：默认 c_int restype 会把失败标记 0xFFFFFFFF 折叠成 -1，导致错误检测失效；现声明 restype=c_uint32（惰性初始化，不影响非 Windows 导入）。
- 新增公开常量（FILE_ATTRIBUTE_* 等，保留旧私有名别名）和 `clear_readonly()` 助手（清只读位并返回原属性位，供写动作"先清除、完成后恢复"使用）。

**wstamp/copier.py**
- `copy_stamp`：先取源的时间快照**再**复制（复制读取会刷新源 atime）；用 `utime(ns=...)` 让目标 mtime_ns/atime_ns 与源逐纳秒相等（原实现只写秒级且 atime=mtime）；时间戳之后再整体设置源的全部 Win32 属性位（只读、隐藏等原样搬运；属性先设会导致只读目标无法 utime）。目标已存在且只读时先清只读再覆写。
- 新增 `apply_copy(src, dst, snap, attrs)`：目录树同步在比较字节后复用，使用比较**之前**取得的快照落盘时间戳，避免比较用的读取污染目标时间戳。

**wstamp/sync.py**
- `SyncReport` 新增 `restamped` 列表。
- 条目状态按契约定义为 `(字节内容, mtime_ns)` 二元组：补上了缺失的关键分支——字节相同但 mtime 不同时只回写目标时间戳（atime 取读取内容之前的目标快照原样写回，即使卷启用了 atime 更新也能保持不变），记入 `restamped`；(字节, mtime) 全等则不做任何动作。
- created/updated 通过 copy_stamp/apply_copy 携带纳秒级时间戳与源属性位；对只读目标：覆写先清只读、最终属性以源为准，回写时间先清只读、完成后恢复原属性位，删除（含只读目录树，自底向上清位后 rmtree）先清属性再删。只有 stamp_file 直接报错。
- 无法完成的条目（目标被独占锁定、目标位置被同名目录占据、子树目录无法创建等）记入 `failed` 并继续，不再中断整次同步（原实现 makedirs 冲突会直接崩溃）。
- 报告路径保持相对 dst 的 `os.path.join` 风格（Windows 反斜杠），非绝对路径。
- 新增 `_restore_dir_times`：同步/删除条目会刷新父目录 mtime，故在条目填充完成后按源恢复目录 mtime，`os.walk(topdown=False)` 保证先深层后浅层、根目录最后，使目标树目录（含空目录、根目录）mtime 与源逐纳秒一致。
- `dry_run=True` 计算同样报告但零写入：不建目录、不复制、不覆写、不删除、不写时间戳/属性。