# Oracle control -- wfflab__wciocp-220

`reference/wciocp/` is the reference implementation of the same public API the
candidate package exposes. It is injected over `environment/workspace/wciocp` by
`solve.ps1` at Golden-control time and never enters the agent container.

## What the reference does differently

The shipped module is the frozen defective state of the completion layer; each of
its five defects has exactly one fix in the reference. Module names below are the
real ones under `environment/workspace/wciocp/` and
`verifier/oracle/reference/wciocp/`.

| defect | shipped module | reference |
|---|---|---|
| 1. where a completion comes from | `pool.py` hands notifications over through a **process-local list**: a delivery thread polls each outstanding request's kernel event, appends an `Event` to `_staging`, and `take()` moves that list into `_ready` and pops from it, with `_fallback()` re-handing the most recent notification when the list looks empty. Several `take()` callers scanning one list hand the same notification to two of them, or lose it entirely | `take()` is exactly one `GetQueuedCompletionStatus` call. The queue belongs to the kernel and the module keeps no completion list at all, so "exactly once" is the kernel's atomic dequeue rather than a lock this layer has to get right |
| 2. where the completion key comes from | `pool.py` builds the notification as `Event(self._key_of(handle), ...)`: the key is looked up in the pool's own per-handle dictionary at the moment the notification is *formed*, so a later `register()` rewrites the key of a completion that had already arrived | the key travels **inside the packet**; `take()` reports the value the kernel returned. Each `Request` additionally snapshots the key that was current at `submit()` time, and the reference does the real kernel bind on the first `register()` (see below), so a notification already at the port keeps the key it was submitted under |
| 3. what a missed deadline does | `pool.py` `take()` treats an expired deadline as a pool failure: it sets the degraded flag `_dropped`, clears the list it was reading from, and `_deliver` then refuses to record anything for the rest of the pool's life -- one timeout kills the port | a deadline is `GetQueuedCompletionStatus` returning `FALSE` with `WAIT_TIMEOUT` (258). Nothing is removed from the port: packets that had already arrived are still handed out by the next `take()`, and packets that arrive later are delivered normally |
| 4. capability of the object | `kinds.py` `is_overlapped()` returns `True` for every object, and `pool.py` `register()` trusts it, so a handle opened without `FILE_FLAG_OVERLAPPED` is accepted silently and the read degrades into a synchronous one that never reaches the port | `register()` and `submit()` call `require_overlapped()`, which reads the file object's own mode through `ntdll!NtQueryInformationFile(FileModeInformation = 16)` (`0x0` asynchronous versus `0x20 FILE_SYNCHRONOUS_IO_NONALERT`) and raises `WCIOCPError(kind="unsupported")` for a synchronous object, `badarg` when the handle names no object |
| 5. what closing the pool does | `pool.py` `close()` only flips a flag: because the delivery path refuses to record anything once that flag is set, the reads that were still outstanding are never handed back as `cancelled`, and notifications already sitting in the process-local list can still be drawn from a closed pool | `close()` is idempotent, cancels what is still outstanding so a posted read is taken off the wire (cancel-on-close), and refuses further use: `take()` and `submit()` raise `WCIOCPError(kind="closed")`. The cancelled request's terminal state comes from `995 ERROR_OPERATION_ABORTED` and is reported as `status="cancelled"` |
| `errors.py`, `__init__.py` | left as shipped: the reference updates the `WCIOCPError` docstring and adds the optional `error` attribute to its `__str__` details, and its package docstring describes the completion port, but none of that is graded | the callable names and signatures, `WCIOCPError.KINDS == ("unsupported", "badarg", "os", "timeout", "closed")` and the `Event` status vocabulary (`"completed"` / `"cancelled"`) are identically available from both. A candidate that never touches these two files loses nothing |

Two measured environment limits shape the reference and are worth knowing when
reading it:

* `GetFileInformationByHandleEx(FileModeInformation)` is deliberately **not**
  the mode query used by the reference: on this host it answers 24/87 instead of
  the file mode. The reference reaches the same kernel state through
  `ntdll!NtQueryInformationFile`, which returns the mode word directly.
* `GetQueuedCompletionStatusEx` (the batched dequeue) raises an access violation
  on this host, so the reference dequeues one packet per
  `GetQueuedCompletionStatus` call instead of batching.

## Why the reference records the key itself

Windows fixes a handle's completion key at the handle's **first bind**. A second
`CreateIoCompletionPort(handle, port, newKey, 0)` returns `NULL` with
`ERROR_INVALID_PARAMETER` (87) -- to the same port, to another port, and for a
`DuplicateHandle` copy alike -- and
`NtSetInformationFile(FileCompletionInformation)` answers `0xC000000D`. The
reference therefore calls `CreateIoCompletionPort` exactly once per handle, on
its first `register()`, and after that only records the newly registered key for
that handle. Both facts together are what acceptance criterion A asks for: the
key reported with a notification is the one the kernel was given for that
request, and a later `register()` cannot rewrite a notification that was already
on its way.

## Verified difference

Measured against the hidden suite `verifier/tests/test_wciocp_semantics.py`,
which performs every measurement itself and never takes the candidate's word for
its own correctness:

| case (F2P) | shipped module | reference |
|---|---|---|
| `f2p-completion-key-is-the-registered-one` | the key is read out of the pool's own dictionary when the notification is formed, so nothing ties the reported key to the packet the kernel dequeued | the packet's own key comes back: a handle registered with `0xA1` produced `key=0xa1` |
| `f2p-each-completion-is-delivered-once` | notifications travel through a process-local list that every taker scans, so four concurrent takers duplicate or lose packets | a drain of 8 completions from 4 concurrent takers measured `packets=8 unique=8 duplicates=[] missing=[]` |
| `f2p-keys-distinguish-handles-on-one-port` | only the latest key recorded per handle survives a second registration, so the keys of two handles on one port can cross | two handles on one port each kept their own key: `key=0xa1` and `key=0xb2` came back on the requests that belonged to them |
| `f2p-reregistered-key-does-not-rewrite-past-completions` | `register(handle, new_key)` overwrites the dictionary entry, so a notification that had already reached the port is relabelled with the new key | `early key=1 / late key=2`: the completion that had already arrived kept the earlier key while the request submitted after the re-registration reported the new one |
| `f2p-timeout-does-not-drop-queued-completions` | an expired deadline marks the pool spent and clears what it held, and later completions are refused | on an empty port `take(timeout=0.3)` raised `timeout` and nothing was lost -- work submitted afterwards came back normally |
| `f2p-non-overlapped-handle-is-unsupported` | every object is reported as capable, so a plain (non-overlapped) file handle is registered instead of rejected | `register()` on a handle opened without `FILE_FLAG_OVERLAPPED` raised `WCIOCPError(kind="unsupported")` |
| `f2p-close-rejects-further-use` | `close()` only flips a flag: nothing takes the outstanding reads off the wire, so a request that was pending when the pool closed is never handed back as `cancelled` | `close()` is idempotent; `take()` and `submit()` raise `closed` afterwards, and the outstanding request came back with `status='cancelled'` |

The suite's own summary of that comparison, because the evaluator reaches each
verdict independently:

| observation made by the suite | shipped module | reference |
|---|---|---|
| key reported for a request on a handle registered with `0xA1` | the module's recorded value for that handle, not the packet's | `0xA1` from the kernel packet |
| two handles registered on one port with `0xA1` / `0xB2` | keys can cross because only the last recorded key per handle is used | each request came back with its own handle's key |
| 4 takers draining the same set of completions | duplicate or lost packets, since every taker scans the same list | each submitted read observed exactly once |
| `take(timeout=0.3)` on an empty port | pool marked spent, later notifications dropped | `WCIOCPError(kind="timeout")`, port untouched |
| `register()` against a handle without `FILE_FLAG_OVERLAPPED` | accepted, degrades to a synchronous read | `WCIOCPError(kind="unsupported")` |
| `close()` with a read still outstanding | flag only; no `cancelled` completion, stale notifications still drawable | idempotent; `closed` afterwards; the read comes back `status="cancelled"` |
| invalid arguments and handles | `badarg` for the unusable cases | 11 invalid-argument forms all rejected as `badarg` |

Reference for each verdict: `verifier/tests/test_wciocp_semantics.py`, with the
required case ids in `tests/required_testcases.json` and the rubric conditions in
`verifier/rubric.conditions.json`.

The contract is graded on real Windows only. Scope statement, verbatim: the contract only exists on a real Windows kernel; POSIX epoll/kqueue and io_uring model completion differently and are not an equivalent implementation.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\verifier\oracle\solve.ps1 `
    -TaskRoot C:\task -WorkspaceRoot C:\task\environment\workspace
```

The reference payload is resolved from `-ReferenceRoot`, then
`$env:wciocp_REFERENCE_ROOT`, then the copy next to the script
(`oracle/reference/wciocp`), then
`C:\verifier\wfflab__wciocp-220\oracle\reference\wciocp`, then
`C:\solution\reference\wciocp`, then the package-root sibling
`outside_harbor-verifier\wfflab__wciocp-220\oracle\reference\wciocp` -- the
order `solve.ps1` actually applies. When none of them holds a payload the script
exits 1 rather than grading the shipped module as if it were the reference.
