修复了 `wscan` 包在 Windows 上的三个文件身份缺陷，只改动了实现代码（`wscan/scan.py`、`wscan/dupes.py`），公开 API 签名与模块布局不变，tests/ 未触碰。

**wscan/scan.py**
1. 新增 `_check_root(root)`：root 不是已存在目录时抛 `WScanError(kind="root")`（`scan_tree` 与 `dedupe` 共用）。
2. 新增 `_is_reparse(st)`：用 `os.lstat` / `DirEntry.stat(follow_symlinks=False)` 的 `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT(0x400)` 识别重解析点——junction 的 `os.path.islink` 返回 False，靠 islink 判定必然漏判；非 Windows 平台退化为 `S_ISLNK`。
3. 新增 `_walk_files(root)`：用 `os.scandir` 迭代式遍历（栈，不用递归），**不进入任何重解析点目录**（其内部条目一律不产出，也不会因 junction 指回上层而无限遍历），重解析点文件不产出，普通文件产出。关键实测点：Windows 上 `DirEntry.stat(follow_symlinks=False)` 的 `st_ino/st_dev/st_nlink` 恒为 0，因此对文件另调 `os.stat()` 取真实身份与大小。
4. `scan_tree` 改为：校验 root → 用 `_walk_files` 收集 → `total_bytes` 为所有普通文件 `st_size` 之和 → `hard_link_groups` **按 `(st_dev, st_ino)` 文件身份分组**（原来按 `(size, mtime)`，会把同大小同修改时间的普通文件误判为硬链接）；簇内排序、簇间按首路径排序。

**wscan/dupes.py**
1. 复用 `_check_root` / `_walk_files`，因此 junction 内部文件既不参与 sha256 分组也不会被替换。
2. 新增 `_clear_readonly`：替换前清除目标的 `FILE_ATTRIBUTE_READONLY`，否则 `os.replace` 报 WinError 5（这就是现网"对只读重复文件直接崩溃"的原因）。
3. 新增 `_link_over(canonical, target)`：改用「`os.link(canonical, 同目录唯一临时名)` + `os.replace(临时名, target)`」落位，取代原来的 `os.link(canonical, dup)`（目标已存在必抛 `FileExistsError`/WinError 183，导致首次运行即崩）；临时名用 pid+uuid 生成并做 lexists 检查，异常路径下 `_remove_quietly` 保证清理，成功时随 replace 消失。canonical 只读时对 `os.link` 的 PermissionError 再兜底清一次只读。
4. `dedupe`：canonical = 簇内相对路径字典序最小者；对簇内**身份与 canonical 不同**的路径逐个替换，身份已相同的（本来就是硬链接）跳过且不计入返回值；返回已排序的被替换相对路径。

**验证**（真实 Windows + `mklink /J`）：可见冒烟测试 2 passed；另用一次性临时脚本（已删除，未留在仓库）覆盖了：junction 重复计入/自指环遍历、目录与文件符号链接、同大小同 mtime 的非硬链接不产生簇、跨目录硬链接簇排序、dedupe 对普通/只读 dup、canonical 只读、已有硬链接对、junction 目标不被改动、无临时残留、二次运行幂等、root 校验（不存在/文件/空串）。工作区最终仅有这两个文件的改动。