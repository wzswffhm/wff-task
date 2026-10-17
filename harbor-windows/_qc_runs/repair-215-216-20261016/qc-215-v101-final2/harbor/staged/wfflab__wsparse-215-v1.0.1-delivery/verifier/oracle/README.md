# Oracle control -- wfflab__wsparse-215

`reference/wsparse/` is the reference implementation of the same public API the
candidate package exposes. It is injected over
`environment/workspace/wsparse` by `solve.ps1` at Golden-control time and is
never part of the delivered package.

## What the reference does differently

| module | shipped module | reference |
|---|---|---|
| `alloc.py` | reserves the tail by writing `b"\x00" * n` through the file object | `DeviceIoControl(FSCTL_SET_SPARSE)` then `SetFilePointerEx` + `SetEndOfFile` |
| `usage.py` | returns `os.stat(path).st_size` | `GetCompressedFileSizeW` |
| `ranges.py` | returns `[(0, size)]` for every non-empty file | `DeviceIoControl(FSCTL_QUERY_ALLOCATED_RANGES)` |
| `flags.py` | reports the current state and never writes the attribute | `DeviceIoControl(FSCTL_SET_SPARSE)` with the requested value |
| `_winapi.py` | binds `GetCompressedFileSizeW` only, and never calls it | binds the whole surface the contract needs |
| `errors.py`, `__init__.py` | unchanged | unchanged |

## Verified difference

Measured inside `mcr.microsoft.com/windows/servercore:ltsc2022` (Hyper-V
isolation, Windows Server 2022 build 20348, NTFS, 64 KiB sparse unit):

| observation | shipped module | reference |
|---|---|---|
| `preallocate(1 GiB)` physical size | 1 GiB | 0 B |
| `fsutil sparse queryflag` | `This file is NOT set as sparse` | `This file is set as sparse` |
| `disk_usage` on a 64 MiB sink with two written extents | 67108864 | 131072 |
| `allocated_ranges` on the same sink | `[(0, 67108864)]` | `[(0, 65536), (33554432, 65536)]` |
| `sparse_flag(path, True)` return value | `False` | `True` |

`fsutil file queryAllocRanges offset=0 length=67108864` on the reference sink
reports `Allocated range[0]: Offset: 0x0 Length: 0x10000` and
`Allocated range[1]: Offset: 0x2000000 Length: 0x10000`, which is the same
verdict the reference returns -- the evaluator reaches it independently.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\verifier\oracle\solve.ps1 `
    -TaskRoot C:\task -WorkspaceRoot C:\task\environment\workspace
```

The reference payload is resolved from `$env:WSPARSE_REFERENCE_ROOT`,
`C:\verifier\wfflab__wsparse-215\oracle\reference\wsparse` or
`C:\solution\reference\wsparse`, in that order.
