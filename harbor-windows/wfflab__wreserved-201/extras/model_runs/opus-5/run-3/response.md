修复 Windows 保留设备名和尾部字符处理问题：

1. **rules.py**：修改 `is_reserved()` 按 Win32 规则提取第一个点之前的基名进行判断，正确识别 `CON.txt`、`lpt1.tar.gz` 等保留名，同时允许 `console.txt`、`COM10.log` 等合法名称

2. **sanitize.py**：在净化流程中增加尾部点和空格的清理步骤（调用 `rstrip(" .")`），确保 `report.` 和 `report` 映射到同一个落盘名，避免 Windows 静默丢弃导致的冲突；截断后再次清理以防产生新的尾部字符；净化后为空时明确抛出 `InvalidNameError`

所有原有测试通过，三个核心场景验证通过。