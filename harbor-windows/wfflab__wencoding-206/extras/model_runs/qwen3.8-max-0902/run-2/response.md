## 问题定位

在真实 Windows（系统 ANSI 代码页，本机为 cp936）下复现了三类现象：

1. `wtextio/codec.py` 的 `ALIASES` 把 `default` / `utf8` / `utf-8` 都映射成 `None`，即把编码交给 `open()` 的平台默认值。在英文系统（cp1252）上写中文直接抛 `UnicodeEncodeError`；在中文系统上写出的 `名称` 是 GBK 字节 `b'\xc3\xfb\xb3\xc6'` 而不是 UTF-8；读侧同样按 ANSI 代码页解码，读一个外部 UTF-8 文件得到 `铻轰笣` 这样的乱码。
2. `utf-8-bom` / `utf-8-sig` 被映射成普通 `utf-8`，BOM 既不写入也不剥离，模块里定义的 `BOM_ENCODING` 常量成了死代码。
3. `wtextio/writer.py` 依赖 `open(newline="\r\n")` 做换行翻译，而 Python 只翻译 `\n`：文本本身已带 CRLF 时（`write_lines` 拼接的内容、`append_text`、调用方传来的 Windows 文本）落盘变成 CR CR LF，仓库自带的 `tests/test_wtextio_basic.py::test_append` 因此在修改前就是失败的，也违背「落盘换行固定为 CRLF」。

## 修改内容（仅 `wtextio/` 内实现代码）

- `wtextio/codec.py`：`ALIASES` 的值一律改成显式编码名 —— `default`/`utf8`/`utf-8` → `DEFAULT_ENCODING`（`utf-8`），`utf-8-bom`/`utf-8-sig` → `BOM_ENCODING`（`utf-8-sig`）；`ansi`/`latin-1`/`cp1252` 及未知名称原样透传的行为不变，键集合不变（`known_encodings()` 结果不变）。同步更新文档字符串，说明默认编码与平台无关、`system_encoding()` 仅供诊断。
- `wtextio/writer.py`：新增内部 `_collapse_crlf()`，写入/追加前先把已有 CRLF 折叠成 LF，再交给 `open(newline=...)` 展开，保证落盘换行恰好是一个 CRLF（混合 `\r\n`/`\n` 的输入也统一为 CRLF）。`newline` 参数仍然生效（传 `\n` 就落 LF）。
- `wtextio/reader.py`：行为不变（仍走 `encoding_for`、`newline=""` 不做换行翻译），只补充文档说明读取默认编码与写入一致。

未改动任何公开签名与返回值语义（`write_text`/`append_text` 仍返回字符数，`write_lines` 的返回语义按「不改变既有公开接口」的要求原样保留），未引入第三方依赖，`tests/` 未增删改，工作区无遗留临时文件。

## 验证

- `python -m pytest tests/ -q`：5 passed（含此前失败的 `test_append`）；在 `PYTHONUTF8=0`（平台默认 cp936）下同样 5 passed。
- 在 cp936 环境逐条核对验收标准：① 写中文不抛异常且 `p.read_bytes() == text.encode('utf-8')`；② 默认参数读回等于原文；③ 外部生成的 UTF-8 文件（含 `café`、中文）读取正确、`read_lines` 正确；④ `encoding='utf-8-bom'` 落盘以 `EF BB BF` 开头，`detect_bom` 返回 `utf-8`，用同编码可读回原文；⑤ `write_text`/`append_text`/`write_lines` 落盘换行均为 CRLF。
- 另外把 `locale.getpreferredencoding` 伪造成 `cp1252` 后写入中文，落盘仍是 UTF-8，证明结果不再随平台默认编码变化。