# Verifier side -- wfflab__wciocp-220

This directory never enters the agent container. It carries:

- `tests/test_wciocp_semantics.py` -- the hidden behavioural suite for the
  Windows completion-port contract. Every assertion is backed by a measurement
  the suite performs itself: it creates its own named pipes with
  `CreateNamedPipeW(..., PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED)` and its own
  `CreateFileW` client ends, registers each handle with **its own** completion
  key through the candidate's `register`, issues its own pending reads through
  the candidate's `submit`, then drains the port with four threads calling
  `take` at the same time. The verdict for a request is "it came back exactly
  once, carrying the key that was registered for its handle" -- a value the
  candidate returns is never used as the reference for its own correctness. The
  suite even writes into its own client ends to confirm the byte counts.

  **This file ships twice.** Harbor copies `tests/` into the container at
  `C:\tests` for the verifier step, and `tests/run_tests.ps1` resolves the suite
  from there; the copy under `verifier/` is the delivered record of what was
  graded. The two copies must stay byte-identical -- a mismatch means the graded
  suite is not the recorded one. Both copies currently hash to
  `67126ff13818d1378454c697535f1bcaeb7543430d41a52461031479b75fe515`
  (SHA256, `-Algorithm SHA256` over each file).
- `oracle/reference/wciocp/` -- the reference payload. `oracle/solve.ps1`
  installs it over the candidate package for the Golden control.
- `rubric.conditions.json` -- the machine-readable conditions behind
  `tests/rubric.json`: five programmatic items whose weights sum to `1.0` and
  which together cover the 14 required cases (F2P 7 / P2P 7, listed in
  `tests/required_testcases.json`).
- `ISOLATION.md` -- how the boundary is enforced and re-checked.
- `negative_access_probe.ps1` -- proves the boundary from inside a container.
- `evidence/` -- the control-run evidence for the two arms, kept under
  `evidence/golden/` and `evidence/no_change/`. The directories are part of the
  delivery and are currently empty in this tree: the control runner is what
  populates them, so an empty directory means "no run captured here", not "the
  run produced nothing".

## Windows completion-port mechanism anchors

`metadata/windows_mechanism.json` records the counterfactual, the exclusive
declaration, the mechanism anchors (each bound to a verbatim clause of
`instruction.md`, a `test_ref` into the hidden suite and one F2P case) and the
environment-layer anchor that makes a host without the required completion-port
capability fail the readiness probe instead of silently grading the candidate.

The facts the whole task rests on, all measured in the pinned image:

* `kernel32!CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 0)` creates the
  port. `kernel32!CreateIoCompletionPort(handle, port, key, 0)` binds a handle
  to it and registers the **completion key** -- a `ULONG_PTR` the kernel keeps
  for that handle itself.
* `kernel32!GetQueuedCompletionStatus(port, &bytes, &key, &ov, timeout)`
  dequeues **one packet atomically**. The packet carries the key *the kernel
  copied at completion time*, the `OVERLAPPED*` of the request and the transfer
  count. The queue belongs to the kernel; the module holds no user-mode
  completion list, so "one notification is delivered to exactly one taker" is a
  kernel guarantee rather than a lock this layer has to invent. That is also why
  the key can never honestly be looked up in the module's own dictionary.
* Waiting on an empty port ends as `FALSE` with `WAIT_TIMEOUT` (258) and removes
  nothing: whatever had already been queued stays queued for the next call.
  A deadline that expires therefore cannot damage the port.
* The terminal state of a dequeued request is read back with
  `GetOverlappedResult`: `995 ERROR_OPERATION_ABORTED` is how a request that was
  taken off the wire identifies itself, and it is what becomes
  `status == "cancelled"`. `996 ERROR_IO_INCOMPLETE` would mean the request is
  somehow still outstanding.
* Whether an object can carry completions at all is decided by the file object's
  kernel mode, not by `GetFileType`: a handle opened without
  `FILE_FLAG_OVERLAPPED` accepts an `OVERLAPPED*` and quietly completes as a
  synchronous read, so no packet ever reaches the port. The reference reads that
  mode with `ntdll!NtQueryInformationFile(FileModeInformation = 16)` -- an
  asynchronous object reports `Mode = 0x0`, a synchronous one reports `0x20
  FILE_SYNCHRONOUS_IO_NONALERT`.
  `GetFileInformationByHandleEx(FileModeInformation)` is **not usable here**: on
  this host it returns 24/87 and cannot answer the question.
* Windows fixes a handle's completion key at its **first bind**. A second
  `CreateIoCompletionPort(handle, port, newKey, 0)` returns `NULL` with
  `ERROR_INVALID_PARAMETER` (87) -- to the same port, to another port, and for a
  `DuplicateHandle` copy alike -- and
  `NtSetInformationFile(FileCompletionInformation)` answers `0xC000000D`. The
  reference therefore performs the real kernel bind on the **first**
  `register()` and only records the key afterwards; every `Request` snapshots
  the key that is current at `submit()` time, and `Event.key` takes the value
  the kernel handed back. Acceptance criterion A is observable precisely because
  of this: a later `register()` cannot relabel a notification that has already
  reached the port.
* Cancelling on close is a separate, narrow use of the mechanism:
  `kernel32!CancelIoEx(handle, OVERLAPPED*)` is what takes a request that is
  still outstanding off the wire when the pool is closed, so its completion
  comes back as `status == "cancelled"`. This is cancel-on-close only -- the
  graded contract is the key/delivery/timeout/capability behaviour above, not
  per-request cancellation.
* `GetQueuedCompletionStatusEx` (the batched dequeue variant) raises an access
  violation on this host, so the reference does not use it: one packet per
  `GetQueuedCompletionStatus` call is enough.
* Scope statement, verbatim: the contract only exists on a real Windows kernel; POSIX epoll/kqueue and io_uring model completion differently and are not an equivalent implementation.

## Environment preflight

`environment/validate_environment.ps1` asserts the same facts before anything is
scored: the host is a Windows kernel (`Win32NT`), a completion port can be
created and a named pipe bound to it, a read that was pending on that pipe
finishes and its packet arrives at the port carrying the registered key and the
right byte count, and a second, empty wait reports `WAIT_TIMEOUT` (258). Any
failure exits 1: the environment is INVALID, never a candidate score of 0.
