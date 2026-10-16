# wcancel

Overlapping (asynchronous) reads with per-object cancellation.

The collector reads large inputs by handing several reads to the operating system
at once instead of blocking on one read at a time. A download is split into
shards; each shard is one overlapping read of the same source object, and a user
who drops a shard asks the module to abandon that shard.

```python
from wcancel import submit, cancel, wait

request = submit(source_handle, size=65536, offset=shard_start)
if user_dropped_the_shard:
    cancel(request)
completion = wait(request, timeout=5.0)
print(completion.status, completion.bytes_read)
```

## API

| name | meaning |
|---|---|
| `submit(handle, size, offset=0)` | start one overlapping read and return the `Request` for it |
| `cancel(request)` | abandon one outstanding read; `True` when the read has been given up |
| `cancel_all(handle)` | abandon every outstanding read on `handle`; returns how many were given up |
| `wait(request, timeout=None)` | wait for one read and return its `Completion` |
| `is_overlapped(handle)` | whether the object can carry overlapping operations |
| `handle_kind(handle)` | `file` / `pipe` / `console` / `unknown` |
| `WCancelError` | carries a `kind` of `unsupported` / `badarg` / `os` / `timeout` |

A `Request` exposes `handle`, `size` and `offset`. A `Completion` exposes
`bytes_read` and `status`, where `status` is `"completed"` or `"cancelled"`.

## Supported platforms

The read layer runs on Windows; the objects it reads from are opened for
overlapping use by the caller. `docs/NOTES.md` describes how the module was
originally laid out and is kept for history only.

## Tests

```
python -m pytest tests -q
```
