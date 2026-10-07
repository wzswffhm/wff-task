修复了 wdl 在 Windows NTFS 环境下处理备用数据流的三个关键问题：

1. **streams.py**: 修复 `stream_size` 函数，现在返回备用数据流本身的字节数，而不是主文件的大小。改用 `stream_path(path, name)` 获取流的实际大小。

2. **unblock.py**: 修复 `unblock` 函数的幂等性，现在调用 `remove_stream` 而不是直接 `os.remove`，对没有标记的文件返回 `False` 而不是抛出 FileNotFoundError。

3. **archive.py**: 修复 `copy_file` 函数，现在在复制主文件后会遍历 `PORTABLE_STREAMS` 列表，将所有备用数据流（包括 Zone.Identifier）一并复制到目标文件。`archive_tree` 因为调用了 `copy_file`，自动继承了这个能力。

所有修改均使用标准库，保持了公开接口签名不变，通过了现有测试并满足全部验收标准。