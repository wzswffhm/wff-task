修复了 wsafename 在 Windows 文件系统上的三个关键问题：

1. **正确识别保留设备名**：修改 `rules.py` 中的 `is_reserved()` 函数，按 Win32 规则只检查第一个点之前的基名。现在 `CON.txt`、`con.tar.gz` 会被正确识别为保留名，而 `console.txt`、`com10.log` 则正常放行。

2. **规范化尾部点和空格**：修改 `sanitize.py`，在净化过程中去除 Windows 会静默丢弃的尾部点和空格。现在 `report.` 和 `report` 会得到相同的落盘名 `"report"`，避免清单与磁盘不一致。

3. **提前拒绝空名称**：净化后不再剩下可用字符时（如 `"..."`、`"   "`）直接抛出 `InvalidNameError`，不再让底层 OSError 透传给调用方。

所有既有测试通过，已验证三个目标场景均符合预期。