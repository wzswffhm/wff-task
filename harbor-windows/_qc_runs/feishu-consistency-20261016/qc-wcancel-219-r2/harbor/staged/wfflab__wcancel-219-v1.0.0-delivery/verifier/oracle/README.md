# Oracle control -- wfflab__wcancel-219

`reference/wcancel/` is the reference implementation of the same public API the
candidate package exposes. It is injected over `environment/workspace/wcancel` by
`solve.ps1` at Golden-control time and never enters the agent container.

## What the reference does differently

The shipped module is the frozen defective state of the read layer; each of its
five defects has exactly one fix in the reference.

| module | shipped module | reference |
|---|---|---|
| `_winapi.py` | binds `CancelIo(handle)`, which takes the requests the **calling thread** issued on the handle; from another thread it returns `TRUE` and cancels nothing | binds `CancelIoEx(handle, OVERLAPPED*)`, which names one request and works from any thread; reads each request's terminal state with `GetOverlappedResult`, where `995 ERROR_OPERATION_ABORTED` means aborted, `996 ERROR_IO_INCOMPLETE` means still outstanding and `1168 ERROR_NOT_FOUND` means no longer outstanding |
| `proc.py` | `cancel()` ignores the target request, calls the handle-wide `CancelIo`, and returns `True` even for a request that had already completed | `cancel()` calls `CancelIoEx` with **that request's** `OVERLAPPED`, returns `True` only when a cancellation actually went out, returns `False` on `ERROR_NOT_FOUND` (request already finished, including a second cancel of the same request), and may be called from any thread; `cancel_all(handle)` loops over the requests this module submitted on the handle |
| `proc.py` (`wait`) | treats `ERROR_OPERATION_ABORTED` as an ordinary `WCancelError(kind="os")`, so a cancelled request can never be reported as `status="cancelled"` | maps `ERROR_OPERATION_ABORTED` onto `Completion(0, "cancelled")`, so cancellation is a terminal state of its own and never an I/O failure; each request is awaited on its own `OVERLAPPED.hEvent` via `WaitForSingleObject`, so waiting on one request never disturbs another |
| `proc.py` (`submit`) | never asks whether the object can carry an overlapped request | calls `require_overlapped()` first and raises `WCancelError(kind="unsupported")` for a handle opened without `FILE_FLAG_OVERLAPPED`, instead of letting the read quietly run synchronously |
| `kinds.py` | `is_overlapped()` always returns `True` | reads the file object's own mode (`FileModeInformation`, i.e. `Mode = 0x0` asynchronous versus `0x20 FILE_SYNCHRONOUS_IO_NONALERT` synchronous) and answers from that; `badarg` when the handle names no object |
| `errors.py`, `__init__.py` | left as shipped: the reference updates the `WCancelError` docstring and adds the optional `error` attribute to its `__str__` details, and its package docstring describes cancellation, but none of that is graded | the callable names and signatures, `WCancelError.KINDS == ("unsupported", "badarg", "os", "timeout")` and the `Completion` status vocabulary are identically available from both. A candidate that never touches these two files loses nothing |

`GetFileInformationByHandleEx(FileModeInformation)` is deliberately **not** the
mode query used by the reference: on this host it answers 24/87 instead of the
file mode. The reference reaches the same kernel state through
`ntdll!NtQueryInformationFile`, which returns the mode word directly.

## Verified difference

Measured against the hidden suite
`verifier/tests/test_wcancel_semantics.py`, which performs every measurement
itself and never takes the candidate's word for its own correctness:

| case (F2P) | shipped module | reference |
|---|---|---|
| `f2p-cancel-affects-only-the-target-request` | cancellation is issued by handle (`CancelIo`), which takes away the calling thread's requests on that handle; the case's requirement -- the neighbour must stay outstanding and later time out -- cannot hold | only the named request is aborted; the neighbour is still outstanding afterwards |
| `f2p-cancel-works-from-another-thread` | `CancelIo` from the second thread returns success while the request keeps running until the timeout | `CancelIoEx` from the second thread really aborts the request |
| `f2p-cancelled-request-reports-cancelled-status` | `wait()` raises `WCancelError(kind="os")` for `ERROR_OPERATION_ABORTED`; no `status="cancelled"` is ever produced | `wait()` returns `Completion(bytes_read=0, status="cancelled")` |
| `f2p-completed-request-cannot-be-cancelled` | `cancel()` on a finished request still returns `True` | `cancel()` returns `False` (kernel answer `1168 ERROR_NOT_FOUND`) |
| `f2p-second-cancel-reports-false` | the second cancel also returns `True` | the second cancel returns `False`; the state is never `"cancelled"` twice |
| `f2p-non-overlapped-handle-is-unsupported` | `is_overlapped()` states `True` for every object, so a plain (non-overlapped) file handle is accepted and read synchronously instead of raising | `submit()` raises `WCancelError(kind="unsupported")` |
| `f2p-uncancelled-request-still-delivers-the-bytes` | the neighbour's outcome is not the one the case requires, so the byte-exact delivery it asserts is not reported | the uncancelled request completes with the exact bytes written into the pipe |

The suite's own summary of that comparison, because the evaluator reaches each
verdict independently:

| observation made by the suite | shipped module | reference |
|---|---|---|
| terminal state of the request named in `cancel()` | an `os`-kind exception (995 misclassified) | `status="cancelled"` |
| terminal state of the neighbour submitted on the same handle | not the outstanding request the case requires from a same-thread cancel | still outstanding, then completes with the written bytes |
| `cancel()` issued from a second thread | reports `True`, request still pending | reports `True`, request aborted |
| `cancel()` after the request already completed | `True` | `False` |
| `submit()` against a handle without `FILE_FLAG_OVERLAPPED` | accepted, degrades to a synchronous read | `WCancelError(kind="unsupported")` |

Reference for each verdict: `verifier/tests/test_wcancel_semantics.py`, with the
required case ids in `tests/required_testcases.json` and the rubric conditions in
`verifier/rubric.conditions.json`.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\verifier\oracle\solve.ps1 `
    -TaskRoot C:\task -WorkspaceRoot C:\task\environment\workspace
```

The reference payload is resolved from `-ReferenceRoot`, then
`$env:wcancel_REFERENCE_ROOT`, then the copy next to the script
(`oracle/reference/wcancel`), then `C:\verifier\wfflab__wcancel-219\oracle\reference\wcancel`,
then `C:\solution\reference\wcancel` -- the order `solve.ps1` actually applies.
When none of them holds a payload the script exits 1 rather than grading the
shipped module as if it were the reference.
