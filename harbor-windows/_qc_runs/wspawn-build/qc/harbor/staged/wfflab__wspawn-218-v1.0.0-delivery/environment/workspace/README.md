# wspawn

Start sandboxed helper processes with an explicit handover of the parent's
objects.

```python
from wspawn import spawn, set_inheritable

set_inheritable(log_pipe_write, True)
helper = spawn(["C:\\Python312\\python.exe", "worker.py"], inherit=[log_pipe_write])
helper.wait()
```

## API

| name | meaning |
|---|---|
| `spawn(argv, inherit=(), stdin=None, stdout=None, stderr=None)` | start a helper and hand it the listed objects |
| `set_inheritable(handle, enabled=True)` | mark an object as transferable to children |
| `is_inheritable(handle)` | whether an object is currently transferable |
| `inheritable_handles()` | every transferable object in this process |
| `handle_kind(handle)` | `file` / `pipe` / `console` / `unknown` |
| `WSpawnError` | carries a `kind` of `unsupported` / `os` / `badarg` |

## Supported platforms

The sandbox host runs on Windows and the helpers are Windows processes.
`docs/NOTES.md` describes how the module was originally laid out.

## Tests

```
python -m pytest tests -q
```
