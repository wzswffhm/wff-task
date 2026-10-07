## 问题定位（在本机 Windows / ANSI=cp936 上实测复现）

1. `codec.ALIASES` 把 `default`/`utf8`/`utf-8` 映射成 `None`，等于把编码选择交回 `open()` 的平台默认值 → 写中文抛 `UnicodeEncodeError`（或按 cp936 落盘成非 UTF-8 字节），读 UTF-8 文件解出乱码。
2. `utf-8-bom`/`utf-8-sig` 被映射成普通 `utf-8` → 根本不写 BOM。
3. `encoding_for` 只做 `.lower()`，不认 `UTF_8_BOM` / `utf8bom` / `utf8sig` 这类写法。
4. `writer` 依赖 `open(newline="\r\n")` 做换行翻译，而该翻译只认 `\n`：文本里已有的 `\r\n` 被翻成 `\r\r\n`（实测 `b'a\r\r\nb'`），仓库自带 `test_append` 因此失败；单独的 `\r` 则原样落盘。

## 改动

**`wtextio/codec.py`**
- `ALIASES` 的值全部改为显式编码名：`default`/`utf8`/`utf-8` → `"utf-8"`（即 `DEFAULT_ENCODING`），`utf-8-bom`/`utf-8-sig` → `"utf-8-sig"`（即 `BOM_ENCODING`）；`ansi`/`latin-1`/`cp1252` 保持原样，键集合与 `known_encodings()` 结果不变。
- 新增 `normalize_alias()`：去空白 + 小写 + 忽略 `-`/`_`/空格分隔符，使 `UTF-8-BOM`、`utf_8_bom`、`utf8bom`、`utf8sig`、`LATIN_1` 等写法都能归一识别。
- `encoding_for()` 用归一化键查表：`None`/`""`/`default`/各种 UTF-8 写法固定返回 `"utf-8"`；带 BOM 的写法固定返回 `"utf-8-sig"`；未命中的名称原样透传（如 `cp936`、`shift_jis`）。签名与返回类型不变。
- `system_encoding()` 保留（仅诊断用途），不再影响任何默认行为。

**`wtextio/writer.py`**
- 新增 `normalize_newlines(text, newline="\r\n")`：先把 `\r\n`→`\n`、孤立 `\r`→`\n`，再统一翻成目标序列，因此结果中绝不会出现 `\r\r\n`。
- `write_text` / `append_text` 一律以 `encoding_for(...)` 显式编码 + `newline=""`（关闭 open 的翻译）落盘，换行固定 CRLF；签名（含 `newline="\r\n"` 默认值）与返回字符数的语义保持不变。追加时 utf-8-sig 不会重复插入 BOM（已实测）。
- `write_lines` 改为显式分支，逻辑与原来等价：空列表写出 0 字节文件，否则逐行以 CRLF 结尾。

**`wtextio/reader.py`**
- 只补充文档说明；读取侧仍走 `encoding_for()`，因此默认与写入侧同为 UTF-8（修复"读取用系统 ANSI 代码页"），`newline=""` 的既有语义（原样返回磁盘换行）保持不变。

## 验证结果

- 中文文本落盘字节 == `text.encode("utf-8")`，默认参数读回等于原文；外部生成的 UTF-8 文件（含重音字母）读取正确。
- `encoding="utf-8-bom"`（含 `UTF_8_BOM`/`utf8sig` 等别名）写出的文件以 `EF BB BF` 开头；用 `"utf-8"` 读回保留 `\ufeff`，用 `"utf-8-sig"` 读回剥离 BOM；`detect_bom` 对该文件返回 `"utf-8"`，对无 BOM 文件返回 `None`。
- `"a\r\nb\nc\rd\r\ne"` → `b'a\r\nb\r\nc\r\nd\r\ne'`，无 `\r\r\n`；`write_lines`/`append_text` 同规则；`write_lines(path, [])` → 0 字节。
- `python -m pytest tests/ -q` 5 passed（修复前 `test_append` 失败）。仅使用标准库，断网可运行，未在 `tests/` 下增删任何文件。