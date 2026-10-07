Fixed Windows file naming issues in wsafename library:

1. **Reserved device name detection** (rules.py): Modified `is_reserved()` to check only the basename before the first dot, matching Win32 behavior. Now correctly blocks CON, CON.txt, CON.tar.gz, NUL.log, LPT1.data, etc., while allowing console.txt, mycon, com10.log.

2. **Trailing character normalization** (sanitize.py): Added `rstrip(TRAILING_CHARS)` to remove trailing dots and spaces that Windows silently discards. This ensures `report.` and `report` map to the same file, preventing inventory/disk mismatches. Applied after character replacement and after truncation to handle edge cases.

3. **Validation improvements** (rules.py): Enhanced `is_valid()` to reject names with trailing dots/spaces and names that become empty after stripping those characters, ensuring deterministic behavior.

All existing tests pass. The three main scenarios now work correctly:
- Reserved device names with extensions are blocked before file creation
- Trailing dots/spaces are normalized during sanitization
- Empty-after-sanitization names raise InvalidNameError immediately

No new dependencies added, public API unchanged.