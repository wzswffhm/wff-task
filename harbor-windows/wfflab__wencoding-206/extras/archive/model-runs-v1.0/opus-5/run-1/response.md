Fixed wtextio to use UTF-8 encoding by default on Windows instead of platform ANSI code page.

Changes made:
1. **wtextio/codec.py**: Updated ALIASES mapping to use "utf-8" instead of None for all encoding aliases (default, utf8, utf-8), ensuring UTF-8 is always used regardless of platform.

2. **wtextio/writer.py**: Added _normalize_newlines() helper function to convert all newline variants (\n, \r\n, \r) to a consistent target format. Modified write_text(), append_text(), and write_lines() to:
   - Normalize newlines to CRLF (\r\n) before writing
   - Use newline="" to disable Python's automatic newline translation
   - Ensure all text written to disk uses UTF-8 encoding with CRLF line endings

3. **wtextio/reader.py**: Added newline="" to read_text() to preserve original line endings when reading files.

Results:
- Chinese and accented text now write successfully without UnicodeEncodeError
- Written bytes are correct UTF-8 encoding
- Round-trip (write then read) preserves original text
- External UTF-8 files read correctly
- utf-8-bom encoding works and writes BOM header
- All newlines are consistently converted to CRLF on disk
- All existing tests pass