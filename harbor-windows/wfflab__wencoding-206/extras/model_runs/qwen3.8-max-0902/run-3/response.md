修复 `wtextio` 在 Windows 上按平台默认编码写文本、以及换行翻倍的问题。改动仅限 `wtextio/` 包内三个源文件，未新增第三方依赖，未改动 `tests/`，公开签名保持不变。

## wtextio/codec.py
- 缺陷根因：`ALIASES` 把 `default`/`utf8`/`utf-8` 映射为 `None`，`encoding_for()` 因此返回 `None`，`open()` 退回平台 ANSI 代码页（本机 cp936 / 英文机 cp1252）——中文要么抛 `UnicodeEncodeError`，要么落盘成非 UTF-8 字节；读取侧同样用 ANSI 解 UTF-8 文件得到乱码。
  - 现在 `default`/`utf8`/`utf-8`/`None`/空串 一律映射为 `"utf-8"`，`utf-8-bom`/`utf-8-sig` 映射为 `"utf-8-sig"`（原来错误地映射成 `"utf-8"`，导致写不出 BOM）。`encoding_for()` 永不返回 `None`。
- 别名归一化：新增 `_normalize_key()`（去空白、转小写、去掉 `-`/`_`/空格等分隔符）与派生表 `_NORMALIZED_ALIASES`，因此 `UTF_8_BOM`、`utf8bom`、`utf8sig`、`UTF-8-SIG`、`utf_8` 等写法都能识别；未命中的名称原样透传（如 `gbk`、`cp936`）。`ALIASES` 的键集合与 `known_encodings()` 结果保持不变。
- `ansi` → `mbcs` 在非 Windows 平台（无 `mbcs` codec）优雅回退到该平台 ANSI 编码；`system_encoding()` 仅作诊断用途，不再影响默认行为。

## wtextio/writer.py
- 缺陷根因：写入时依赖 `open(..., newline="\r\n")` 的翻译，文本里已有的 `\r\n` 会变成 `\r\r\n`（仓库自带的 `test_append` 就是因此失败）。
- 现在写入前显式做换行归一化 `normalize_newlines()`：先把 CRLF/CR/LF 折叠成单个 `\n`，再整体替换为目标序列（默认 CRLF），并用 `open(..., newline="")` 阻止解释器二次翻译。`write_text`（含 `newline` 参数：`"\n"`/`""`/`None` 语义与 `open()` 对齐）、`append_text`、`write_lines` 全部遵循同一规则，落盘字节中不会出现 `\r\r\n`。
- 所有写入都传入 `encoding_for()` 解析出的显式编码，默认 UTF-8；`utf-8-bom`/`utf-8-sig` 由标准库 `utf-8-sig` codec 写出 `EF BB BF` 前缀。
- `write_lines`：空列表写出 0 字节文件并返回 0；每行去掉行尾多余换行后补一个 CRLF（避免行自带 `\r\n` 时产生空行），按其文档字符串「返回写入的行数」返回行数。
- `write_text`/`append_text` 仍返回 `len(text)`（既有语义与仓库测试 `test_returns_written_length` 不变）。

## wtextio/reader.py
- 读取侧复用同一套 `encoding_for()`，默认按 UTF-8 解码（不再用系统 ANSI 代码页），保证写/读两端一致、外部生成的 UTF-8 文件也能正确读出；保留 `newline=""`（不在读取时翻译换行）与 `read_lines` 的 `splitlines()` 切分、`detect_bom` 的既有返回值语义（无 BOM 返回 `None`）。
- 用 `"utf-8"`（默认）读带 BOM 的文件保留开头 U+FEFF，用 `"utf-8-sig"`/`"utf-8-bom"` 读则剥离 BOM，符合验收标准 7。

## 验证
在 Windows（本机 ANSI 为 cp936）上用一次性脚本核对全部验收标准：中文/重音文本落盘等于其 UTF-8 字节且不再抛异常、默认参数读回原文、读外部 UTF-8 文件正确、`utf-8-bom`（含 `UTF_8_BOM`/`utf8bom`/`utf8sig` 别名）写出以 `EF BB BF` 开头、换行固定 CRLF 且无 `\r\r\n`、`write_lines` 空列表 0 字节、`detect_bom` 对无 BOM 文件返回 `None`、`encoding_for` 全部映射用例，以及仓库自带 5 个测试的等价断言（其中 `test_append` 修复前失败、修复后通过）。验证脚本与 `__pycache__` 已清理，`git status` 仅显示三个源文件被修改。