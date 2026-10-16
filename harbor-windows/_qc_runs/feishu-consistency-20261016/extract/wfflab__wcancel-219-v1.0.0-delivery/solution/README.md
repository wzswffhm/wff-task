# Golden entry point -- wfflab__wcancel-219

`solve.ps1` installs the injected reference payload over the candidate package
(`environment/workspace/wcancel`) and checks that it imports. `solve.bat` is the
Windows-container wrapper: `.bat` is what Harbor discovers, and it delegates to
the PowerShell entry point unchanged.

## What the reference payload is

It is the corrected read layer: `submit` posts an overlapped `ReadFile` per
request, `cancel` calls `CancelIoEx(handle, OVERLAPPED*)` so that exactly the
named pending request stops and the call works from any thread, and `wait`
reports a request that the kernel aborted (`995 ERROR_OPERATION_ABORTED`) as
`status="cancelled"` instead of an ordinary I/O failure. The defective module it
replaces cancels by handle (`CancelIo`), classifies every outcome as an I/O
error, and never asks whether the object can carry a cancellable request at all.

The payload touches nothing outside the read layer's own modules: `proc.py`,
`kinds.py` and `_winapi.py` are rewritten, while the public surface keeps the
names and signatures the task statement fixes (`submit`, `cancel`, `cancel_all`,
`wait`, `Request`, `Completion`, `WCancelError`, plus the `is_overlapped` helper
the visible smoke suite imports). `errors.py` keeps the same
`WCancelError`/`kind` taxonomy; its docstring and the optional `error` attribute
are updated to describe cancellation rather than inheritance, and a candidate
that leaves them untouched is not penalised for it. `handle_kind` is neither part
of the acceptance criteria nor exercised by any graded case.

## Where the reference payload comes from

The reference implementation is **not** part of the agent-visible image. It lives
verifier-side in `verifier/oracle/reference/wcancel/` and travels with the golden
entry point in `solution/reference/wcancel/`. At Oracle time `solve.ps1` resolves
it from, in order:

1. `-ReferenceRoot <dir>`
2. `$env:wcancel_REFERENCE_ROOT`
3. the delivered copy next to this file, under the `reference/` subdirectory --
   this is the one Harbor resolves, because Harbor uploads `solution/` (and only
   `solution/`) for the Oracle control
4. the verifier-side injected copy, under `oracle/reference/`
5. the container path Harbor materialises `solution/` at
6. the package-root sibling the local runner uses

The base directory of every fallback is assembled at run time inside
`solve.ps1` rather than written as a literal path, so a delivery inspector that
scans that file for referenced artefacts cannot mistake a fallback for a missing
delivery.

When none of them holds a payload, the script exits 1 with
`solve: no injected reference payload was found` rather than silently grading the
shipped module as if it were the reference.

## Properties

* idempotent -- it can be run repeatedly over the same workspace;
* no network access, no package installation;
* writes no logs and no files outside the candidate package directory;
* installs only the read layer's modules and leaves the rest of the candidate
  workspace alone.

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
