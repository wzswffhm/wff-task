修复 wtextio 在 Windows 上按平台默认编码写文本导致非 ASCII 内容损坏的问题，共修改 3 个文件（均在 wtextio/ 包内，未动 tests/）：

1. **wtextio/codec.py** —— 编码策略修复（根因）：
   - `ALIASES` 中 `default` / `utf8` / `utf-8` 原先映射为 `None`（即交给 open() 用平台默认值，Windows 上是 ANSI 代码页 cp1252/mbcs），现固定映射为 `"utf-8"`；`utf-8-bom` / `utf-8-sig` 原先错误映射为 `"utf-8"`，现映射为 `"utf-8-sig"`。
   - `encoding_for` 新增别名归一化：大小写不敏感，且 `-` / `_` / 无分隔符写法等价（`UTF_8_BOM`、`utf8bom`、`utf8sig`、`Utf-8-Sig` 等都能识别）；`None` 固定返回 `"utf-8"`；未命中的名称原样透传。公开签名不变。

2. **wtextio/writer.py** —— 换行归一化修复：
   - 原先 `open(newline="\r\n")` 会把文本中已有的 `\r\n` 翻成 `\r\r\n`。现在先用正则把文本中的 CRLF / LF / CR 统一归一化为 LF，再经 `newline="\r\n"` 转换落盘，保证落盘一定是单个 CRLF、绝不翻倍。
   - `write_text` 返回值仍为原文本字符数（语义不变）；`append_text` 遵循同一归一化规则；`write_lines` 重写为以 `\n` 拼接后复用 `write_text`，逐行落盘 CRLF，空列表写出 0 字节文件并返回 0。

3. **wtextio/reader.py** —— 读取侧：
   - `read_text` / `read_lines` 经修复后的 `encoding_for` 默认按 UTF-8 解码，与写入侧一致；用 `utf-8` 读带 BOM 文件保留 U+FEFF，用 `utf-8-sig`（含 `utf-8-bom` 别名）读则剥离 BOM。
   - `detect_bom` 补充 UTF-32 LE/BE 的识别（在 UTF-16 之前判断，避免 `\xff\xfe\x00\x00` 被误判为 utf-16-le），无 BOM 仍返回 `None`。

验证：仓库自带 5 个测试全部通过；逐条核验了 8 项验收标准（中文/重音文本落盘为 UTF-8 字节、默认参数往返一致、读取外部 UTF-8 文件、BOM 写出与剥离/保留、CRLF 归一化不翻倍、encoding_for 全部映射与别名变体、write_lines/append_text/空列表/detect_bom 行为），全部通过。仅用标准库，无新依赖，断网可运行。