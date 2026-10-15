# wtoken

Audit the privileges held by the current process, and switch them on or off.

```python
from wtoken import privileges, has_privilege, set_privilege

for name, enabled in privileges().items():
    print(name, "on" if enabled else "held but off")

if has_privilege("SeBackupPrivilege"):
    set_privilege("SeBackupPrivilege", True)
    ...
    set_privilege("SeBackupPrivilege", False)
```

Holding a privilege and having it switched on are two different things:
`has_privilege()` answers the first, `privileges()` answers the second.

## API

| name | meaning |
|---|---|
| `privileges()` | `{name: enabled}` for every privilege the token holds |
| `has_privilege(name)` | whether the token holds the privilege at all |
| `set_privilege(name, enabled=True)` | switch a held privilege on or off |
| `privilege_luid(name)` | the identifier the system uses for a name |
| `privilege_name(luid)` | the name for an identifier |
| `elevation()` | `{"elevated": bool, "type": str}` |
| `integrity_level()` | the mandatory integrity level of the token |
| `WTokenError` | carries a `kind` of `unsupported` / `os` / `badarg` |

## Supported platforms

The deployment checker runs on Windows and inspects the process token.
`docs/NOTES.md` describes how the module was originally laid out.

## Tests

```
python -m pytest tests -q
```
