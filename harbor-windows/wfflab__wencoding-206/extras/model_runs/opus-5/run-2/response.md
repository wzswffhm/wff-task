Fixed Windows encoding issues in wtextio by ensuring UTF-8 is always used as the default encoding instead of platform-dependent encodings.

Changes made to wtextio/codec.py:
1. Updated ALIASES mapping to return "utf-8" instead of None for default/utf8/utf-8/None keys, ensuring UTF-8 is always used
2. Changed "utf-8-bom" and "utf-8-sig" mappings to return "utf-8-sig" (Python's BOM-enabled UTF-8) instead of plain "utf-8"
3. Added case-insensitive and separator-agnostic alias normalization (handles UTF_8_BOM, utf8bom, utf8sig, etc.)

Changes made to wtextio/writer.py:
1. Added newline normalization in _normalize_text() to convert all line endings (CRLF/LF/CR) to a single normalized format before writing
2. Used newline='' in all open() calls and manually write b'\r\n' bytes to ensure consistent CRLF line endings on disk
3. Modified write_text(), append_text(), and write_lines() to apply newline normalization before writing

These changes ensure that:
- Chinese and accented characters write correctly as UTF-8 bytes on Windows
- Files can round-trip correctly (write then read produces original text)
- UTF-8-BOM writes actual BOM bytes (EF BB BF) and detect_bom() recognizes them
- All newlines normalize to CRLF without doubling
- Encoding aliases work case-insensitively with various separators
- Empty lists write 0-byte files

All existing tests pass and the implementation meets all acceptance criteria.