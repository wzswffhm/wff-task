Fixed wpublish to properly handle Windows ACL inheritance and permission evaluation:

1. **publish.py**: Added `recursive=True` parameter to the `deny()` call in `publish()` function, ensuring the deny ACE is applied to the entire subtree (root + all subdirectories and files) with inheritance flags (OI)(CI) so newly created files also inherit the restriction.

2. **icacls.py**: 
   - Fixed `list_explicit_aces()` to filter out inherited ACEs by checking the `inherited` flag
   - Fixed `parse_aces()` to properly handle icacls output where the first ACE line includes the path before the principal name

3. **rights.py**: Fixed `can_write()` to respect Windows "deny takes precedence" rule by checking if any write rights are denied before allowing write access.

All existing tests pass and the implementation now correctly:
- Applies deny ACE recursively to entire subtree during publish
- Ensures new files created after publish inherit the deny restriction
- Denies write access when both allow and deny ACEs exist (deny precedence)
- Distinguishes explicit ACEs from inherited ones
- Returns empty audit results after a successful publish