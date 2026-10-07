# wscan：磁盘扫描 / 去重管线的 Windows 文件身份缺陷

`wscan` 是服务器磁盘治理流水线的核心工具，负责「扫描目录树 → 统计
硬链接簇 → 把内容重复的文件替换为硬链接」。它对外承诺**扫描结果
完整且不重复、硬链接簇按真实文件身份分组、去重安全不丢数据**，
但现网反馈（仓库 issue #213）：

1. 在含 junction（目录联接）的目录树上，扫描结果把 junction 指向的
   内容**重复计入**（同一文件出现两份），总字节数翻倍，甚至触发
   死循环般的重复遍历；
2. 硬链接簇的分组不按文件身份，把"恰好同大小同修改时间"的普通
   文件误判成硬链接；
3. `dedupe` 在现网第一次运行就抛 `FileExistsError`，对带只读属性的
   重复文件直接崩溃。

你的任务：修复 `wscan` 包，使它满足下文验收标准中的每一条语义。
所有语义都是**本题已声明的契约**，不需要你猜测额外行为。

## 工作区

```
wscan/
  errors.py      # WScanError（kind 标记）
  scan.py        # ScanResult / scan_tree
  dupes.py       # dedupe
tests/
  test_wscan_basic.py   # 可见的冒烟测试
```

## 背景事实（Windows 特有，契约的直接依据，均已实测）

- **junction 不是符号链接**：对 junction 调 `os.path.islink` 返回
  `False`；`os.walk` **无论 `followlinks=True/False` 都会进入
  junction**（Python 把 junction 当普通目录处理）。重解析点标志
  只能通过 `os.lstat(path)` 或 `DirEntry.stat(follow_symlinks=False)`
  的 `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT (0x400)`
  观察。junction 可用 `mklink /J` 创建，不需要管理员权限。
- **NTFS 硬链接共享同一个文件身份**：`(st_dev, st_ino)` 相同；
  所有路径共享同一份属性与时间戳，经任一路径的修改在所有路径可见。
  `os.stat` 每次调用都返回最新状态，但**旧 stat 对象不会自动刷新**
  （建链前取的 `st_nlink` 永远是旧值）。
- `os.link(src, dst)` 在 `dst` 已存在时抛 `FileExistsError`
  （WinError 183）——目标是同一个文件时也不例外；把新链接"落位"到
  已被占用的名字上要用「先 link 到临时名、再 `os.replace` 回原路径」。
- **只读属性**（`FILE_ATTRIBUTE_READONLY`，0x1）使 `unlink`/`replace`
  失败（WinError 5）；`os.chmod(path, stat.S_IWRITE)` 可清除它。
- `os.stat` 的 `st_ctime` 在 Windows 上是**创建时间**（birth time），
  与 Linux 的 ctime 语义不同。
- 同一时刻连续写入的文件 `st_mtime_ns` 可能相同；需要区分时用
  `os.utime(path, ns=(atime_ns, mtime_ns))` 显式设置。

## 验收标准（全部为已声明契约）

1. **`scan_tree(root) -> ScanResult`**：
   - `root` 不是已存在的目录 → 抛 `WScanError(kind="root")`；
   - **遍历语义**：不进入任何带重解析点的目录（junction、目录符号
     链接），其内部条目一律不统计；带重解析点的文件也不统计；
     普通文件正常统计。该遍历语义对 `dedupe` 同样生效；
   - `files`：相对 `root` 的路径列表（`os.path.join` 风格，
     Windows 下为反斜杠），已排序，不得包含 junction 内部路径；
   - `total_bytes`：`files` 中全部普通文件的 `st_size` 之和；
   - `hard_link_groups`：硬链接簇列表。**按文件身份
     `(st_dev, st_ino)` 分组**——不是按大小/修改时间，也不是按内容；
     每簇 ≥2 个路径、簇内路径已排序；簇列表按簇内首路径排序。

2. **`dedupe(root) -> list[str]`**：
   - `root` 校验与 `scan_tree` 相同（非目录 → `WScanError(kind="root")`）；
   - 遍历语义与 `scan_tree` 相同（不进入重解析点目录）；
   - 按**内容**（sha256）分组，内容相同且路径数 ≥2 的簇：
     - canonical = 簇内相对路径字典序最小的路径；
     - 对簇内每个**文件身份与 canonical 不同**的路径 `dup`：
       若带只读属性先清除；用「`os.link(canonical, 临时名)` +
       `os.replace(临时名, dup)`」把 `dup` 替换为指向 canonical 的
       硬链接；临时名用完即消失；
     - 文件身份已与 canonical 相同的路径（本来就是硬链接）**不动**；
   - 返回被替换的相对路径列表（已排序）；
   - 不得改动 canonical 的内容；替换后该路径的属性与时间戳随
     canonical（NTFS 硬链接属性共享，这是声明过的语义，无需恢复）。

3. **不回归**：不含 junction 的普通树扫描/去重行为正确；重复文件
   去重后内容可读、`st_nlink` 正确；不得改动公开 API 的签名与模块
   布局。

## 测试

- 判分只跑 `tests/test_wscan_semantics.py`（隐藏测试）。
- 任何一条 required 失败 → 本题 0 分；全部通过 → 1 分。
- 测试在真实 Windows 文件系统上运行，junction 用 `mklink /J` 创建，
  文件身份用 `(st_dev, st_ino)` 校验。
