# Oracle control -- wfflab__wtoken-221

`reference/wtoken/` is the reference implementation of the same public API the
candidate package exposes. It is injected over `environment/workspace/wtoken` by
`solve.ps1` at Golden-control time and is never part of the delivered package.

## What the reference does differently

| module | shipped module | reference |
|---|---|---|
| `privileges.py` | shells out to the tool that prints the human-facing privilege table, parses its columns, and reports every row it recognises as `True` | opens the process token with `OpenProcessToken` and reads the array with `GetTokenInformation(TokenPrivileges)`, keeping the attributes word so that "present" and "enabled" stay separate |
| `privileges.py` (`set_privilege`) | raises `unsupported`; never implemented | resolves the LUID with `LookupPrivilegeValue` and writes the enabled bit with `AdjustTokenPrivileges` |
| `privileges.py` (`privilege_luid` / `privilege_name`) | uses the row index inside the parsed table as the identifier | uses the LUID the system assigns, packing it into one integer and unpacking it again |
| `token.py` (`elevation`) | asks for a POSIX superuser id and reports "not elevated" on Windows | reads `TokenElevation` and `TokenElevationType` |
| `token.py` (`integrity_level`) | returns the placeholder `"unknown"` | reads `TokenIntegrityLevel` and names the RID |
| `_winapi.py` | binds only `OpenProcessToken` and `CloseHandle` | binds the whole surface the contract needs |
| `errors.py`, `__init__.py` | unchanged | unchanged |

## Verified difference

Measured inside `mcr.microsoft.com/windows/server:ltsc2022` (the full,
untrimmed Windows Server runtime; os.version 10.0.26100, the same build as the
buyer's Windows 11 hosts; pinned by digest in `task.toml`) under Hyper-V
isolation. The token in that image holds 24 privileges, of which 4 are
enabled. These figures describe the run recorded with the delivered jobs; they
must be re-confirmed whenever the base image or task hash changes, because a
different Windows build can present a different privilege set:

| observation | shipped module | reference |
|---|---|---|
| a privilege the token holds but has switched off | reported as `True` (held and enabled collapsed) | reported as `False`, while `has_privilege` still says `True` |
| `set_privilege("SeShutdownPrivilege", False)` then `GetTokenInformation` | the call raises `unsupported`, the attribute word is untouched | the attribute word loses `SE_PRIVILEGE_ENABLED` |
| `privilege_luid("SeShutdownPrivilege")` | the row index in the parsed table | `19` (LUID 0x13), the value the system uses |
| `elevation()["elevated"]` | `False` | `True` (`TokenElevation` is 1 in this image) |
| `integrity_level()` | `"unknown"` | `"High"` |

The evaluator reaches those verdicts on its own: it opens the token, reads the
privilege array and the attribute words, and re-reads them after driving the
candidate.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\verifier\oracle\solve.ps1 `
    -TaskRoot C:\task -WorkspaceRoot C:\task\environment\workspace
```

The reference payload is resolved from `$env:WTOKEN_REFERENCE_ROOT`,
`C:\verifier\wfflab__wtoken-221\oracle\reference\wtoken` or
`C:\solution\reference\wtoken`, in that order.
