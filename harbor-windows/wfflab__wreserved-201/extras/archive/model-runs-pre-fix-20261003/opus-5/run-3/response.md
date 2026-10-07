修复了 wsafename 在 Windows 文件系统上的三个关键问题：

1. **保留设备名判定** (rules.py)：修改 `is_reserved()` 按 Win32 规则只检查第一个点之前的基名，现在 `CON.txt`、`lpt1.tar.gz` 等会被正确拒绝，而 `console.txt`、`com10.log` 可正常使用。

2. **尾部点与空格规范化** (sanitize.py, rules.py)：在 `sanitize()` 中添加 `rstrip(TRAILING_CHARS)` 步骤，确保 `report.` 与 `report` 得到相同的落盘名；`is_valid()` 也检查去除尾部字符后是否为空。

3. **净化后空名称拒绝** (sanitize.py)：净化后若不剩可用字符会立即抛出 `InvalidNameError`，而非让底层 I/O 失败。

所有既有测试通过，三项验收标准均已满足。