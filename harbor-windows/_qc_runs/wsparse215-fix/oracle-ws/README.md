# wsparse

Space management for the collector's on-disk sink files.

```python
from wsparse import preallocate, disk_usage, allocated_ranges

preallocate("sink.bin", 1 << 30)   # reserve a gigabyte for the writer
disk_usage("sink.bin")             # how much disk that sink really holds
allocated_ranges("sink.bin")       # which byte ranges are already on disk
```

## API

| name | meaning |
|---|---|
| `preallocate(path, size)` | grow `path` to `size` bytes and reserve the space |
| `disk_usage(path)` | bytes `path` occupies on disk |
| `allocated_ranges(path)` | `[(offset, length), ...]` backed by clusters |
| `sparse_flag(path, enabled=True)` | turn the sparse attribute on or off |
| `sparse_state(path)` | whether `path` carries the sparse attribute |
| `WSParseError` | carries a `kind` of `unsupported` / `os` / `badarg` |

## Supported platforms

The collector ships on Windows and the sinks live on NTFS. `docs/NOTES.md`
describes how the module was originally laid out.

## Tests

```
python -m pytest tests -q
```
