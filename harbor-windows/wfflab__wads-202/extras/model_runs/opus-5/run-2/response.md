修复了 wdl 在处理 NTFS 备用数据流时的三个核心问题：

1. **archive.py** - `copy_file` 现在会遍历 `PORTABLE_STREAMS` 并复制所有备用数据流（包括 `Zone.Identifier`），确保归档后的文件保留来源标记。

2. **streams.py** - `stream_size` 修正为对流路径调用 `os.path.getsize`，返回流自身的字节数而非主文件大小。

3. **unblock.py** - `unblock` 改用 `remove_stream` 实现，对不存在流的文件返回 `False` 而非抛异常，实现幂等性；`is_blocked` 改用 `stream_exists` 以保持一致。

所有修改仅限 `wdl/` 包内的实现代码，未改动测试文件，通过了全部既有测试并验证了归档保留流、体积计算准确、解除标记幂等等真实场景。