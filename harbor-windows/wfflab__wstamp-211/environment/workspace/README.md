# wstamp

带 Windows 语义的文件时间戳 / 属性工具库（内部备份流水线依赖它保证
「目标树的字节与修改时间都和源一致」）。

- `snapshot_times(path)` —— 读取一个路径的时间戳快照
- `stamp_file(path, mtime_ns)` —— 把 mtime 精确设置为整数纳秒
- `copy_stamp(src, dst)` —— 复制文件并携带时间戳与文件属性
- `sync_tree(src, dst, dry_run=False)` —— 目录树同步，返回 `SyncReport`

已知问题：备份流水线反馈「同步完成后，与源内容相同的目标文件修改时间
仍然停留在几天前」「目录时间戳对不上」，见仓库 issue #211。
