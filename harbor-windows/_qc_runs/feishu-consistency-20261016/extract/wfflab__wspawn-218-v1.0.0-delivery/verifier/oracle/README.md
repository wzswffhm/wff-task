# Oracle control -- wfflab__wspawn-218

`reference/wspawn/` is the reference implementation of the same public API the
candidate package exposes. It is injected over `environment/workspace/wspawn` by
`solve.ps1` at Golden-control time and is never part of the delivered package.

## What the reference does differently

| module | shipped module | reference |
|---|---|---|
| `proc.py` | `subprocess.Popen(..., close_fds=False)`; the `inherit` argument is stored and then ignored | `CreateProcessW` with `EXTENDED_STARTUPINFO_PRESENT`, an attribute list built by `InitializeProcThreadAttributeList` and `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` holding exactly the named handles |
| `inherit.py` | calls `os.set_inheritable` / `os.get_inheritable` on an **object handle**, which is a descriptor-level API | `SetHandleInformation` / `GetHandleInformation` with `HANDLE_FLAG_INHERIT` |
| `kinds.py` | always returns `"unknown"` | `GetFileType` mapped onto `file` / `pipe` / `console` / `unknown` |
| `_winapi.py` | binds `GetFileType` only | binds the whole surface the contract needs |
| `errors.py`, `__init__.py` | unchanged | unchanged |

## Verified difference

Measured inside `mcr.microsoft.com/windows/servercore:ltsc2022` (Hyper-V
isolation, Windows Server 2022 build 20348):

| observation | shipped module | reference |
|---|---|---|
| a second inheritable pipe that was **not** named in `inherit` | usable from the child (the write succeeds) | not present in the child at all |
| `inherit=[]` with two inheritable pipes open | both pipes cross the boundary | nothing crosses |
| `set_inheritable(handle, True)` then `GetHandleInformation` | the flag is unchanged, and the call itself fails because the handle is not a descriptor | the flag is set, observable from outside |
| `handle_kind(pipe_write_handle)` | `"unknown"` | `"pipe"` |
| handle value seen by the child | same number, but every object is reachable | same number, and only the named object is reachable |

The evaluator reaches those verdicts on its own: it creates the pipes, reads the
inherit flag with `GetHandleInformation`, and has the child report in-band which
handle it could write to.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\verifier\oracle\solve.ps1 `
    -TaskRoot C:\task -WorkspaceRoot C:\task\environment\workspace
```

The reference payload is resolved from `$env:WSPAWN_REFERENCE_ROOT`,
`C:\verifier\wfflab__wspawn-218\oracle\reference\wspawn` or
`C:\solution\reference\wspawn`, in that order.
