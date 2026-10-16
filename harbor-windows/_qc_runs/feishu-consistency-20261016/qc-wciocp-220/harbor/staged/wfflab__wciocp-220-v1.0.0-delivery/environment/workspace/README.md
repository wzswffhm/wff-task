# wciocp

A completion pool for the collector's overlapping (asynchronous) reads.

The collector hands several reads to the operating system at once instead of
blocking on one read at a time, and the results are collected again through a
pool shared by its worker threads. Each registered object carries a *completion
key* — the integer that says which collection job it belongs to.

```python
from wciocp import create_pool

pool = create_pool(threads=4)

pool.register(pipe, 0x11)          # this pipe serves job 0x11
pool.register(spool_file, 0x22)    # this file serves job 0x22

request = pool.submit(pipe, size=65536, offset=0)
...
event = pool.take(timeout=5.0)
print(hex(event.key), event.bytes_read, event.status)

pool.close()
```

## API

| name | meaning |
|---|---|
| `create_pool(threads=4)` | build a pool served by `threads` workers |
| `Pool.register(handle, key)` | register an object under the completion key `key` |
| `Pool.submit(handle, size, offset=0)` | start one overlapping read and return its `Request` |
| `Pool.take(timeout=None)` | collect one notification and return its `Event` |
| `Pool.close()` | stop the pool; outstanding reads are cancelled |
| `is_overlapped(handle)` | whether the object can carry overlapping operations |
| `WCIOCPError` | carries a `kind` of `unsupported` / `badarg` / `os` / `timeout` / `closed` |

A `Request` exposes `handle`, `offset` and `size`. An `Event` exposes `key`,
`request`, `bytes_read` and `status`, where `status` is `"completed"` or
`"cancelled"`.

`take()` takes its deadline in seconds; `None` means the caller is willing to
wait for as long as it takes. Several worker threads may call it at the same
time on the same pool.

## Supported platforms

The read layer runs on Windows and takes its objects from the process's pipe and
file factories, which open them for overlapping use.

## Notes and tests

`docs/NOTES.md` describes how the layer was originally put together and is kept
for history only.

```
python -m pytest tests -q
```
