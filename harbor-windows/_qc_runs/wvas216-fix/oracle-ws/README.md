# wvas

Read-only virtual address space audit for the collector's live processes.

```python
from wvas import regions, file_backed_regions, modules

regions(pid)               # every committed and reserved region of pid
file_backed_regions(pid)   # only the regions that a file backs
modules(pid)               # the images loaded into pid
```

## API

| name | meaning |
|---|---|
| `regions(pid, include_reserved=True)` | region descriptors of `pid`, ascending by `base` |
| `file_backed_regions(pid)` | the subset of `regions(pid)` whose `path` is not `None` |
| `modules(pid)` | the images loaded into `pid`, ascending by `base` |
| `protection_name(value)` | Win32 protection constant -> short name |
| `type_name(value)` | Win32 region type constant -> short name |
| `WVasError` | carries a `kind` of `badarg` / `no-such-process` / `access-denied` / `unsupported` / `query-failed` |

`regions()` and `file_backed_regions()` return region descriptors. A descriptor
is a dict with exactly these keys:

| key | meaning |
|---|---|
| `base` | address the region starts at |
| `size` | length of the region |
| `state` | `"commit"` or `"reserve"` |
| `type` | `"image"`, `"mapped"` or `"private"` |
| `protect` | short protection name, as returned by `protection_name()` |
| `path` | the file that backs the region, or `None` when no file backs it |
| `image` | whether the region belongs to a loaded image |

`modules()` returns dicts with `base`, `size` and `path`.

## Reading the answers

The audit runs against real processes, so `regions()` reflects whatever the
target happens to have mapped at the moment of the call.

## Platform

Windows only. `docs/NOTES.md` records how the module grew.

## Tests

```
python -m pytest tests -q
```
