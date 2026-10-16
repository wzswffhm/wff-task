# Oracle control -- wfflab__wvas-216

`reference/wvas/` is the reference implementation of the same public API the
candidate package exposes. It is injected over `environment/workspace/wvas` by
`solve.ps1` at Golden-control time and is never part of the delivered package.

## What the reference does differently

| module | shipped module | reference |
|---|---|---|
| `_winapi.py` | binds `VirtualQueryEx` and `GetMappedFileNameW`, but never binds `QueryDosDeviceW`, so no device-to-drive mapping exists | binds the whole surface the contract needs, including `QueryDosDeviceW` over every drive letter |
| `vas.py` | masks `base` and `size` with `0xFFFFFFFF`, only walks `MEM_COMMIT`, reports no reserved region, returns the raw device path (or an empty string) for a file-backed region, and raises a bare `OSError` when a process cannot be opened | keeps full-width values, reports `MEM_COMMIT` and `MEM_RESERVE`, translates `\Device\...` back to a DOS or UNC path, returns `None` when no file backs the region, and classifies failures into `WVasError` kinds |
| `modules()` | derives the inventory from the region walk and keeps every image region, so one image appears hundreds of times | asks the loader for its module list (`EnumProcessModulesEx` + `GetModuleFileNameExW`), keeps each image once and sorts by base |
| `errors.py`, `__init__.py` | unchanged | unchanged |

## Verified difference

Measured on a real Windows host (Python 3.12, 64-bit) against a target process
that created a file mapping, an anonymous mapping, a 1 MiB private allocation and
a 6 GiB reservation:

| observation | shipped module | reference |
|---|---|---|
| number of reported regions | 393 | 463 |
| highest reported base | `0xece34000` | `0x7ffc8ee08000` |
| regions above 4 GiB | 0 | 461 |
| regions with `state == "reserve"` | 0 | 70 |
| distinct paths of the form `\Device\HarddiskVolumeN\...` | 59 | 0 |
| regions whose path is the empty string | 20 | 0 |
| missing pid failure | `OSError` (no kind) | `WVasError(kind='no-such-process')` |
| `modules()` entries | 325 | 50 |

The absolute numbers depend on the machine; the defects do not. The graded suite
re-measures everything itself, so none of the values above is baked into a test.

The `modules()` row is the one that needed care inside a container. There the
loader maps images from a VSMB share, so `GetMappedFileNameW` answers with
`\Device\vmsmb\VSMB-{...}\{...}\Files\...`, a prefix no DOS device covers. The
reference therefore builds the inventory from the loader's own module list, which
answers with the DOS path (`C:\Python312\python.exe`) on both a host and inside
the container, and the region walk is only required to name what it can name.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\verifier\oracle\solve.ps1 `
    -TaskRoot C:\task -WorkspaceRoot C:\task\environment\workspace
```

The reference payload is resolved from `$env:WVAS_REFERENCE_ROOT`,
`C:\verifier\wfflab__wvas-216\oracle\reference\wvas` or
`C:\solution\reference\wvas`, in that order.
