修复了 wsafename 在 Windows 环境下的三个关键问题：

1. **保留设备名判定**：修改 `rules.py` 中的 `is_reserved()` 函数，按 Win32 规则只检查第一个点之前的 basename。现在 `CON.txt`、`con.tar.gz` 会被正确识别为保留名并拒绝，而 `console.txt`、`com10.log` 可以正常使用。

2. **尾部点和空格处理**：修改 `sanitize.py`，在净化流程末尾添加 `rstrip(TRAILING_CHARS)` 去除 Windows 会自动丢弃的尾部点和空格。现在 `report.` 和 `report` 会得到同一个落盘名，避免清单与磁盘内容不一致。

3. **空名称明确拒绝**：将空名称检查移到去除尾部字符之后，确保 `...`、`   ` 等净化后为空的输入会抛出 `InvalidNameError`，而不是把底层 OSError 透传给调用方。

所有既有测试通过，三个场景的验收标准均已满足。