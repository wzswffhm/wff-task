Fixed wtextio Windows encoding issues by:

1. **codec.py**: Changed ALIASES to map "default"/"utf8"/"utf-8"/None to "utf-8" instead of None, and "utf-8-bom"/"utf-8-sig" to "utf-8-sig" instead of "utf-8". Added normalize_encoding_name() to handle case-insensitive aliases with various separators (-, _, or none) for utf8/utf8bom/utf8sig variants.

2. **writer.py**: Added _normalize_newlines() helper to unify CRLF/LF/CR to LF first, then replace with target CRLF. Updated write_text(), append_text(), and write_lines() to normalize embedded newlines before writing, using newline="" in open() to prevent Python's automatic conversion. This ensures no CRLF doubling and consistent CRLF on disk.

3. **reader.py**: No changes needed - already uses encoding_for() which now returns correct UTF-8 encoding.

All acceptance criteria verified:
- Chinese and accented text write without errors as UTF-8 bytes
- Roundtrip with default parameters works correctly
- External UTF-8 files read properly
- utf-8-bom (and aliases like UTF_8_BOM, utf8bom) write BOM correctly
- All newlines normalize to CRLF on disk without doubling
- BOM detection and reading behavior correct
- Empty lists create 0-byte files
- All existing tests pass