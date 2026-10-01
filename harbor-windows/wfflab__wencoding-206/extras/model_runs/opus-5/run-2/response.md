修复 wtextio 在 Windows 上的编码问题：

1. **codec.py**: 修改 ALIASES 字典，将 "default"、"utf-8"、"utf8" 从 None 改为 "utf-8"，确保默认使用 UTF-8 编码而非平台默认编码；将 "utf-8-bom" 和 "utf-8-sig" 正确映射到 "utf-8-sig"。

2. **writer.py**: 添加 _normalize_newlines() 函数统一处理换行符，将所有换行符（\n、\r、\r\n）标准化为 CRLF；修改 write_text、append_text 使用 newline="" 参数禁用 Python 的自动换行转换，手动确保所有输出都是 CRLF。

修复后的行为：
- 写入中文等非 ASCII 内容不再抛异常，落盘字节是标准 UTF-8
- 默认参数读写的文件可以正确往返
- 可以正确读取外部生成的 UTF-8 文件
- encoding="utf-8-bom" 正确生成带 BOM 的 UTF-8 文件
- 所有换行固定为 CRLF

所有既有测试通过，未修改任何测试文件。