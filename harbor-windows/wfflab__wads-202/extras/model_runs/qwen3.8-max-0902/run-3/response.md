修复了 `wdl` 在 NTFS 备用数据流（ADS）处理上的三个缺陷，只改动 `wdl/` 包内源码（`streams.py`、`archive.py`、`unblock.py`），未触碰 tests/，无新增第三方依赖，公开签名与既有语义保持不变。

1) `wdl/archive.py` —— 归档丢流（现象 1）
   - `copy_file` 之前只调用 `shutil.copy2`，而 Windows 上 `shutil.copyfile` 走的是读/写循环，只搬主数据，`Zone.Identifier` 流被留在源文件上。现在复制主数据后调用新增的私有辅助 `_copy_streams`，按 `PORTABLE_STREAMS` 逐条把流按字节搬到目标（`read_stream` + `write_stream`），源上没有而目标残留的流会被 `remove_stream` 清掉，保证目标与源一致。
   - 辅助函数 `_stream_target` 处理 `dst` 是已存在目录的情形（此时 `copy2` 实际落在目录内部），避免把流写到目录路径上。
   - `archive_tree` 无需改动，复用 `copy_file`，因此嵌套子目录中的文件同样保留备用流。

2) `wdl/streams.py` —— 流大小取错（现象 2）
   - `stream_size` 原来返回 `os.path.getsize(path)`，即宿主文件主数据的大小；改为对 `stream_path(path, name)` 取 `os.path.getsize`，返回流本身的字节数，流不存在（或 stat 失败）仍返回 `0`。
   - `stream_exists` 改用 `os.stat` + 捕获 `OSError/ValueError`，比 `os.path.isfile` 更稳（同样支持目录上的 ADS、空流，宿主文件不存在时返回 False）；`read_stream`/`remove_stream` 统一复用它，`remove_stream` 额外容忍 `FileNotFoundError` 竞态。`read_stream` 在流缺失时仍抛 `StreamError`，`write_stream` 行为不变。

3) `wdl/unblock.py` —— 解除标记不幂等（现象 3）
   - `unblock` 原来无条件 `os.remove(path:Zone.Identifier)`，对干净文件抛 `FileNotFoundError`；改为直接复用 `remove_stream`，带标记时清除并返回 `True`，无标记（含宿主文件不存在）返回 `False` 且不抛异常。`is_blocked` 改用 `stream_exists`。

验证（Windows/NTFS，用 `python -c` 一次性执行，未在仓库留下任何临时文件）：copy_file 后 `Zone.Identifier` 存在且内容与源逐字节一致（流 26 字节 / 主数据 30 字节区分正确）；archive_tree 对 `sub/`、`sub/deep/` 下文件均保留流，`stream_size` 返回 60 而非主数据 1；`unblock` 对带标记文件返回 True、再次调用与对干净/不存在文件均返回 False 且不抛异常；仓库自带 4 个测试全部通过。运行产生的 `__pycache__`/`.pytest_cache` 已清理，`git status` 仅剩三个实现文件的修改。