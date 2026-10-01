## 根因

`wtextio.codec.ALIASES` 把「默认」这一类别名解析成了 `None`／错误的编码名，而 `open()` 收到 `encoding=None` 时会退回**平台默认编码**（Windows 上是当前 ANSI 代码页）。三条现象同源：

| 别名 | 修改前 | 后果 |
|---|---|---|
| `default` / `utf8` / `utf-8` | `None` | 落盘用 ANSI 代码页：中文抛 `UnicodeEncodeError`，重音字母写成 cp1252 字节；读回 UTF-8 文件成乱码 |
| `utf-8-bom` / `utf-8-sig` | `"utf-8"` | 根本不写 BOM |

顺带发现第二个缺陷：`write_text`/`append_text` 以 `newline="\r\n"` 打开，而 `TextIOWrapper` 会把写入的每个 `\n` 再翻译成 `\r\n`，文本里原有的 CRLF 因此落盘成 `\r\r\n`（多一个回车，`read_lines` 每行之间夹空行）。仓库自带的 `test_append` 在修改前就是**失败**的。

## 改动（仅 `wtextio/` 三个文件，未动 tests/）

**`codec.py`**：`default`/`utf8`/`utf-8` → `DEFAULT_ENCODING`（`"utf-8"`），`utf-8-bom`/`utf-8-sig` → `BOM_ENCODING`（`"utf-8-sig"`）。别名键集合、`encoding_for`/`system_encoding`/`known_encodings` 的签名与语义均未变，`ansi` 仍为 `mbcs`，未知名称仍原样透传；只是不再有任何别名解析为 `None`。

**`writer.py`**：新增 `_for_disk()`，在换行翻译生效时先把文本里的 `\r\n` 折叠为 `\n`，交给 `open()` 统一翻译成 CRLF —— 磁盘上换行恰好是 CRLF，混用 `\r\n`/`\n` 的文本也被归一；调用方显式传 `newline=""`/`"\n"`（不翻译）时文本原样写入，`newline` 参数语义保持不变。另加 `_append_encoding()`：`utf-8-sig` 编码器每开一次流都会吐 BOM，往非空文件追加时会在文件中间插进 BOM 造成乱码，故仅在文件为空／新建时写 BOM。`write_lines` 改为返回**行数**，与其自身 docstring「返回写入的行数」一致（此前错误地返回字符数；`write_text` 仍返回字符数，`test_returns_written_length` 通过）。

**`reader.py`**：仅补文档说明；读取侧与写入侧共用 `encoding_for`，故编码修复自动生效。`newline=""` 的既有行为保持不变（不做换行翻译）。

## 验证

- `python -m pytest tests -q` → 5 passed（改前 1 failed）；`python -X utf8=0 -m pytest`（平台默认编码变为 cp936）同样 5 passed。
- 逐条验收：写中文不再抛异常且 `open(p,'rb').read() == text_with_crlf.encode('utf-8')`；默认参数读回得原文；读外部生成的 UTF-8 文件得原文（同环境下裸 `open()` 会得到 `澶栭儴 UTF-8 caf茅` 这类乱码）；`encoding="utf-8-bom"` 落盘以 `EF BB BF` 开头且 `detect_bom()` 返回 `"utf-8"`；落盘换行固定 CRLF、无 `\r\r\n`。
- 用 monkeypatch 记录 `open()` 实参，确认所有读写调用都拿到显式编码名，**没有一次是 `None`**，即结果不再依赖平台代码页。
- 未引入第三方依赖，断网可运行；已清理 `__pycache__`/`.pytest_cache`，`git status` 只显示三个源文件被修改。
