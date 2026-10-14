# Verifier side -- wfflab__wspawn-218

This directory never enters the agent container. It carries:

- `tests/test_wspawn_semantics.py` -- the hidden behavioural suite. Every
  assertion is backed by a measurement the suite performs itself: it creates its
  own anonymous pipes with `CreatePipe`, flips and reads the inherit bit with
  `SetHandleInformation` / `GetHandleInformation`, launches a child **through the
  candidate's** `spawn`, and asks that child in-band which of the two pipes it
  could actually write to -- then reads its own pipe ends to confirm what really
  crossed. A value returned by the candidate is never used as the reference for
  its own correctness.

  **This file ships twice.** Harbor copies `tests/` into the container at
  `C:\tests` for the verifier step, and `tests/run_tests.ps1` resolves the suite
  from there; the copy under `verifier/` is the delivered record of what was
  graded. The two copies must stay byte-identical -- a mismatch means the graded
  suite is not the recorded one.
- `oracle/reference/wspawn/` -- the reference payload. `oracle/solve.ps1`
  installs it over the candidate package for the Golden control.
- `rubric.conditions.json` -- the machine-readable conditions behind
  `tests/rubric.json`.
- `ISOLATION.md` -- how the boundary is enforced and re-checked.
- `negative_access_probe.ps1` -- proves the boundary from inside a container.
- `evidence/verifier-run/` -- the captured control run.

## Windows handle-handover mechanism anchors

`metadata/windows_mechanism.json` records the counterfactual, the exclusive
declaration, the mechanism anchors (each bound to a verbatim clause of
`instruction.md`, a `test_ref` into the hidden suite and one F2P case) and the
environment-layer anchor that makes a host without the required process-creation
capability fail the readiness probe instead of silently grading the candidate.

The two facts the whole task rests on, both measured in the pinned image:

* a child created with handle inheritance enabled receives **every** handle that
  carries the inherit flag, so "just start a process and hope" leaks the parent's
  entire open object set into the helper;
* narrowing that set requires an extended `STARTUPINFO` carrying a handle list
  (`PROC_THREAD_ATTRIBUTE_HANDLE_LIST`), which the Python standard library cannot
  express at all -- `subprocess.Popen` has no parameter for it.
