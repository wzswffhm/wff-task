# Golden entry point -- wfflab__wciocp-220

`solve.ps1` installs the injected reference payload over the candidate package
(`environment/workspace/wciocp`) and checks that it imports. `solve.bat` is the
Windows-container wrapper: `.bat` is what Harbor discovers, and it delegates to
the PowerShell entry point unchanged.

## What the reference payload is

It is the corrected completion layer. `pool.py` creates one I/O completion port
per pool with `CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 0)`; the first
`register(handle, key)` binds that handle with
`CreateIoCompletionPort(handle, port, key, 0)`, which is also where the kernel
records the handle's **completion key**, and every later `register()` only
records the new key (Windows refuses to re-bind an already-bound handle). Each
`submit()` posts one `OVERLAPPED` `ReadFile` and snapshots the key that is
current at that moment, so a request carries the key it was submitted under. Each
`take()` call is exactly one `GetQueuedCompletionStatus`, and `Event.key` is the
value the kernel handed back in the packet -- the whole reason a notification can
never be relabelled by a later registration. A deadline is `WAIT_TIMEOUT` (258),
which leaves the port untouched, and `close()` is idempotent, cancels whatever is
still outstanding (cancel-on-close) and refuses further use with
`WCIOCPError(kind="closed")`, handing a cancelled read back as
`status="cancelled"`.

The defective module it replaces distributes notifications through a
process-local list, looks the key up in its own dictionary instead of taking it
from the packet, marks the pool spent after one missed deadline, never asks
whether an object can carry completions at all, and treats `close()` as a flag
that leaves the outstanding reads behind.

The payload touches nothing outside the completion layer's own modules:
`pool.py`, `kinds.py` and `_winapi.py` are rewritten, while the public surface
keeps the names and signatures the task statement fixes (`create_pool`,
`Pool.register`, `Pool.submit`, `Pool.take`, `Pool.close`, `Event`, `Request`,
`WCIOCPError`, plus the `is_overlapped` helper the visible smoke suite imports).
`errors.py` keeps the same `WCIOCPError`/`kind` taxonomy
(`unsupported` / `badarg` / `os` / `timeout` / `closed`); its docstring and the
optional `error` attribute are updated to describe completion handling, and a
candidate that leaves them untouched is not penalised for it.

## Where the reference payload comes from

The reference implementation is **not** part of the agent-visible image. It lives
verifier-side in `verifier/oracle/reference/wciocp/` and travels with the golden
entry point in `solution/reference/wciocp/`. At Oracle time `solve.ps1` resolves
it from, in order:

1. `-ReferenceRoot <dir>`
2. `$env:wciocp_REFERENCE_ROOT`
3. the delivered copy next to this file, under the `reference/` subdirectory --
   this is the one Harbor resolves, because Harbor uploads `solution/` (and only
   `solution/`) for the Oracle control
4. the verifier-side injected copy, `C:\verifier\wfflab__wciocp-220\oracle\reference\wciocp`
5. the container path Harbor materialises the payload at, `C:\solution\reference\wciocp`
6. the package-root sibling the local runner uses,
   `outside_harbor-verifier\wfflab__wciocp-220\oracle\reference\wciocp`

The base directory of every fallback is assembled at run time inside
`solve.ps1` rather than written as a literal path, so a delivery inspector that
scans that file for referenced artefacts cannot mistake a fallback for a missing
delivery.

The candidate workspace is resolved in the same style: an explicit
`-WorkspaceRoot`, then `$env:wciocp_WORKSPACE_ROOT`, then `C:\testbed`, then
`<TaskRoot>\environment\workspace`.

When no candidate workspace is found the script exits 1 with
`solve: no candidate workspace was found (looked at C:\testbed and the package layout)`.
When none of the payload locations holds one, it exits 1 with
`solve: no injected reference payload was found; the Oracle control cannot run`
rather than silently grading the shipped module as if it were the reference.

## Properties

* idempotent -- it can be run repeatedly over the same workspace (`robocopy /MIR`
  over the read layer only);
* no network access, no package installation;
* writes no logs and no files outside the candidate package directory;
* installs only the completion layer's modules and leaves the rest of the
  candidate workspace alone.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File solution\solve.ps1 `
    -TaskRoot <package root> -WorkspaceRoot <package root>\environment\workspace
```

Then run the scoring entry point on the same workspace:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test.ps1 `
    -TaskRoot <package root> -WorkspaceRoot <package root>\environment\workspace
```

Expected on the reference payload: `run_validity = VALID`, `invalid = 0`,
`formal_score = 1`, i.e. 14/14 required testcases passed (F2P 7 / P2P 7, see
`tests/required_testcases.json`). Every required case gates the score, so any
failure collapses it to 0 rather than to partial credit.

The same run made these observations, which are the ones the graded cases rest
on: two handles on one port kept their own keys (`key=0xa1`, `key=0xb2`);
8 completions drained by 4 concurrent takers measured `packets=8 unique=8
duplicates=[] missing=[]`; the re-registration scenario reported `early key=1 /
late key=2`; an empty port raised `timeout` after 0.30 s and lost nothing;
a handle opened without `FILE_FLAG_OVERLAPPED` was rejected as `unsupported`;
`close()` was idempotent, left `take`/`submit`/`register` raising `closed`, and
returned the outstanding request with `status='cancelled'`; and 11
invalid-argument forms were all rejected as `badarg`.

The contract is graded on real Windows only. Scope statement, verbatim: the contract only exists on a real Windows kernel; POSIX epoll/kqueue and io_uring model completion differently and are not an equivalent implementation.
