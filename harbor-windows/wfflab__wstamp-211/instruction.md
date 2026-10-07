# wstamp：备份流水线的时间戳同步缺陷

`wstamp` 是备份流水线依赖的文件时间戳 / 属性工具库。它对外承诺
「目标树的字节与修改时间都和源一致」，但现网反馈（仓库 issue #211）：
同步完成后，与源内容相同的目标文件 mtime 仍停留在几天前；目录时间戳
也对不上；复制出来的文件丢了只读 / 隐藏属性；时间戳精度只有秒级。

你的任务：修复 `wstamp` 包，使它满足下文验收标准中的每一条语义。
所有语义都是**本题已声明的契约**，不需要你猜测额外行为。

## 工作区

```
wstamp/
  errors.py      # WStampError（kind 标记）
  attributes.py  # Win32 文件属性的读取 / 设置
  stamps.py      # snapshot_times / stamp_file / set_times
  copier.py      # copy_stamp
  sync.py        # SyncReport / sync_tree
tests/
  test_wstamp_basic.py   # 可见的冒烟测试
```

## 功能边界

- **需要处理**
  - 时间戳的读取与纳秒级设置（NTFS 的存储粒度是 100ns）
  - Windows 文件属性（只读 / 隐藏）的搬运与写保护语义
  - 目录树同步的状态比较、报告与目录时间戳恢复
- **不需要处理**
  - 时间戳的自动探测 / 冲突合并策略
  - FAT 卷的 2 秒粒度、硬链接、符号链接、ADS
  - 网络路径与卷挂载点

## 验收标准（全部为已声明契约）

1. **`snapshot_times(path)`** 返回 dict：`mtime_ns`、`atime_ns`（整数纳秒）、
   `created`。`created` 取 `st_ctime`——在 Windows 上这是文件创建时间
   （birth time），与 Linux 的 ctime 语义不同。

2. **`stamp_file(path, mtime_ns)`** 把 mtime 精确设置为整数纳秒；
   **只修改 mtime，atime 必须保持原值**。NTFS 以 100ns 为存储粒度，
   传入的纳秒值应是 100 的倍数，存储后必须逐纳秒相等。
   目标带只读属性时不做任何写动作，抛 `WStampError(kind="readonly")`
   （Windows 对只读文件的 `utime` 会失败，WinError 5）。

3. **`copy_stamp(src, dst)`** 复制单个文件后，目标的 `mtime_ns` 与
   `atime_ns` 必须与源**逐纳秒相等**；源的全部 Win32 属性位
   （只读、隐藏等）必须原样出现在目标上。注意先取源的时间快照再复制
   （复制动作可能更新源的 atime），属性设置必须放在时间戳之后
   （只读目标无法 `utime`）。

4. **`sync_tree(src, dst, dry_run=False)`** 的每个文件条目状态定义为
   **`(字节内容, mtime_ns)` 二元组**：
   - 目标缺失 → 复制内容 + 时间戳 + 属性，记入 `created`；
   - 字节内容不同 → 覆写 + 时间戳 + 属性，记入 `updated`；
   - **字节内容相同但 mtime_ns 不同 → 只回写目标的时间戳（保持目标
     atime 不变），记入 `restamped`**——这是「同步状态包含 mtime」的
     直接推论，也是最容易被漏掉的分支；
   - 目标多余 → 删除（只读条目先清属性再删），记入 `deleted`；
   - 其他无法完成的条目（如目标被占用、目标位置被同名目录占据）→
     记入 `failed`，**不得中断整次同步**。

5. **报告格式**：`SyncReport` 的 `created / updated / restamped / deleted /
   failed` 都是相对 `dst` 的路径（`os.path.join` 风格，Windows 下为
   反斜杠），不得是绝对路径。

6. **目录时间戳**：同步会在目标创建条目，这会刷新父目录的 mtime。
   因此目录的 mtime 必须在条目填充**完成之后**从源恢复（先深层后浅层），
   使目标树的目录 mtime 与源一致。

7. **`dry_run=True`**：计算同样的报告，但不得改动目标树（不创建、
   不覆写、不删除、不写时间戳）。

8. **对只读目标的写动作**（覆写、回写时间、删除）：先清除只读属性、
   完成后恢复原属性位。只有 `stamp_file` 这个单点 API 按第 2 条
   直接报错——它是调用方显式的时间戳设置入口，不应静默改属性。

## 测试

- 判分只跑 `tests/test_windows_timestamp_semantics.py`（隐藏测试）。
- 任何一条 required 失败 → 本题 0 分；全部通过 → 1 分。
- 测试在真实 Windows 文件系统上运行，属性位用 Win32 API 校验。
