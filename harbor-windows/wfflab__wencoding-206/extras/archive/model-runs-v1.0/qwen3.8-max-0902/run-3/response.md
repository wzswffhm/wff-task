## 问题定位

`wtextio` 在 Windows 上写坏文本的根因集中在 `codec.ALIASES`：

1. `"default"` / `"utf8"` / `"utf-8"` 都被映射成 `None`，而 `encoding_for()` 的文档把 `None` 解释为「交给 `open()` 用平台默认值」。在 Windows 上这就是当前 ANSI 代码页（英文系统 cp1252、中文系统 cp936），于是写中文抛 `UnicodeEncodeError`，写重音字母落盘成 ANSI 字节（拿到 Linux 是乱码），读取侧同理把外部 UTF-8 文件按 ANSI 解码成乱码。
2. `"utf-8-bom"` / `"utf-8-sig"` 被映射成普通 `"utf-8"`，BOM 根本不会写出来。
3. 附带发现（仓库自带测试 `test_append` 在修复前就是失败的）：`write_text`/`append_text` 把文本原样交给 `open(newline="\r\n")`，而该模式会把每个 `\n` 再翻译成 `\r\n`，已经是 CRLF 的行尾被写成 `\r\r\n`，违反「落盘换行固定为 CRLF」。

## 修改内容（仅 `wtextio/` 源码，未动 tests/）

**`wtextio/codec.py`**
- `ALIASES` 中 `default` / `utf8` / `utf-8` 改为 `DEFAULT_ENCODING`（`"utf-8"`），`utf-8-bom` / `utf-8-sig` 改为 `BOM_ENCODING`（`"utf-8-sig"`）；表里不再出现 `None`。
- `encoding_for()` 语义与签名不变，但保证**永远返回明确的编码名字符串**（`None`/空串/`"default"` → `"utf-8"`，别名大小写与首尾空白不敏感，未知名称原样透传）。
- 新增内部辅助 `codec_name()`（用 `codecs.lookup().name` 比较编码是否等价），未加入包的公开导出，公开 API 保持不变。
- 补充模块/函数文档，说明「默认编码固定 UTF-8、不随平台变化」的策略。

**`wtextio/writer.py`**
- 新增 `_translate_newlines()`：先把已有 `\r\n` / `\r` 归一成 `\n`，再统一替换成目标换行，并以 `newline=""`（不翻译）交给 `open()`，彻底消除 `\r\r\n`。`newline` 为 `""`/`"\n"` 时原样落盘，为 `None` 时沿用平台换行语义，非法取值仍像 `open()` 一样抛 `ValueError`。
- `write_text` / `append_text` / `write_lines` 一律走该路径，编码显式传给 `open()`；签名与返回值语义不变。
- `append_text` 在目标文件已有内容时把 BOM 编码降级为普通 UTF-8 续写，避免把 BOM 插到文件中间（新文件/空文件仍写 BOM）。

**`wtextio/reader.py`**
- 逻辑不变（继续用 `encoding_for` + `newline=""`），修复由 `codec` 侧生效：默认读取即 UTF-8；补充文档说明与写入侧共用别名、需要跳过 BOM 时传 `"utf-8-bom"`。`detect_bom` 行为保持原样（UTF-8 BOM 仍返回 `"utf-8"`）。

## 验证

- 仓库自带测试：修复前 `test_append` 失败，修复后 `python -m pytest tests/ -q` → 5 passed。
- 用 `python -X utf8=0`（此机 preferred encoding 为 cp936，即真实 Windows ANSI 场景）验证：写中文落盘字节 == `text.encode("utf-8")`；默认参数读回得到原文；外部 UTF-8 文件（含重音字母与中文）读取正确；`encoding="utf-8-bom"` 文件以 `b"\xef\xbb\xbf"` 开头且 `detect_bom` 返回 `"utf-8"`、可用同别名读回；`\n`/`\r\n`/`\r` 输入统一落盘为单个 CRLF，无 `\r\r\n`；连续 append 结果正确。
- 用 monkeypatch 的 `open` 间谍确认所有文本模式调用都传入显式编码（`utf-8` / `utf-8-sig`），从不传 `None`（唯一无编码的是 `detect_bom` 的二进制打开）。
- 未引入任何第三方依赖，未留下调试脚本或 `__pycache__` 等临时文件。