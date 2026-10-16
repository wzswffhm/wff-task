# Verifier side -- wfflab__wcancel-219

This directory never enters the agent container. It carries:

- `tests/test_wcancel_semantics.py` -- the hidden behavioural suite for the
  per-request cancellation contract. Every assertion is backed by a measurement
  the suite performs itself: it creates its own named pipe with
  `CreateNamedPipeW(..., PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED)` plus a
  `CreateFileW` client end, then issues its own pending reads **through the
  candidate's** `submit`, cancels from a **second thread** using the candidate's
  `cancel`, and reads the request's terminal state back from the kernel --
  `995 ERROR_OPERATION_ABORTED` means the request was aborted, `996
  ERROR_IO_INCOMPLETE` means it is still outstanding, `1168 ERROR_NOT_FOUND`
  means it had already finished. A value returned by the candidate is never used
  as the reference for its own correctness; the suite even writes into its own
  client end to prove that an *uncancelled* request on the same handle still
  delivers exactly the bytes that were written.

  **This file ships twice.** Harbor copies `tests/` into the container at
  `C:\tests` for the verifier step, and `tests/run_tests.ps1` resolves the suite
  from there; the copy under `verifier/` is the delivered record of what was
  graded. The two copies must stay byte-identical -- a mismatch means the graded
  suite is not the recorded one. Both copies currently hash to
  `CE598856452087EBE7063C959194FE5873C2F878338C1397C53609612EF44F2C`
  (SHA256, `-Algorithm SHA256` over each file).
- `oracle/reference/wcancel/` -- the reference payload. `oracle/solve.ps1`
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

## Windows cancellation mechanism anchors

`metadata/windows_mechanism.json` records the counterfactual, the exclusive
declaration, the mechanism anchors (each bound to a verbatim clause of
`instruction.md`, a `test_ref` into the hidden suite and one F2P case) and the
environment-layer anchor that makes a host without the required cancellation
capability fail the readiness probe instead of silently grading the candidate.

The facts the whole task rests on, all measured in the pinned image:

* `kernel32!CancelIoEx(handle, OVERLAPPED*)` cancels **exactly** the request that
  owns the named `OVERLAPPED` block and may be called from **any** thread. Its
  counterpart `kernel32!CancelIo(handle)` only covers the requests the *calling
  thread* issued on that handle, so from another thread it returns `TRUE` while
  cancelling nothing -- a success report for work that never happened.
* A request's terminal state is read back through `GetOverlappedResult` as the
  request's **own** error code: `995 ERROR_OPERATION_ABORTED` for an aborted
  request, `996 ERROR_IO_INCOMPLETE` while it is still outstanding, and
  `1168 ERROR_NOT_FOUND` when it is no longer outstanding at all -- which is why
  cancelling an already finished request reports `False` instead of claiming
  success.
* Each request carries its own `OVERLAPPED.hEvent` (`CreateEventW`) so it can be
  awaited with `WaitForSingleObject` without touching the handle's other
  outstanding reads. The `OVERLAPPED` address is the request's identity, so the
  block has to outlive the call.
* Whether an object can carry a cancellable overlapped request is decided by the
  file object's kernel mode, not by `GetFileType`: a handle opened without
  `FILE_FLAG_OVERLAPPED` accepts an `OVERLAPPED` pointer and quietly completes as
  a synchronous read. The reference reads that mode with
  `ntdll!NtQueryInformationFile(FileModeInformation = 16)` -- an asynchronous
  object reports `Mode = 0x0`, a synchronous one reports `0x20
  FILE_SYNCHRONOUS_IO_NONALERT`. `GetFileInformationByHandleEx(FileModeInformation)`
  is **not usable here**: on this host it returns 24/87 and cannot answer the
  question.
* The contract only exists on a real Windows kernel. POSIX `aio_cancel` and
  `io_uring` model cancellation differently -- `aio_cancel` only applies to the
  `aio_read`/`aio_write` family and typically answers `AIO_NOTCANCELED` for an
  ordinary file descriptor, and `io_uring`'s `IORING_OP_ASYNC_CANCEL` is a
  separate model with separate terminal states -- so neither is an equivalent
  implementation of "stop this one request, keep the neighbours running, and
  report `cancelled` as its terminal state".

## Environment preflight

`environment/validate_environment.ps1` asserts the same facts before anything is
scored: the host is a Windows kernel (`Win32NT`), a named pipe can be created and
opened with `FILE_FLAG_OVERLAPPED`, an empty read on it comes back as
`997 ERROR_IO_PENDING`, and cancelling that one request surfaces as
`995 ERROR_OPERATION_ABORTED`. Any failure exits 1: the environment is INVALID,
never a candidate score of 0.
