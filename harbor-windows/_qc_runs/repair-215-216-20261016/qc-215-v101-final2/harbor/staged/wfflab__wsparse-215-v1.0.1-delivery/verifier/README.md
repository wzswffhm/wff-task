# Verifier side -- wfflab__wsparse-215

This directory never enters the agent container. It carries:

- `tests/test_wsparse_semantics.py` -- the hidden behavioural suite. Every
  assertion is backed by a measurement the suite performs itself: it opens its
  own handles with `CreateFileW`, drives `DeviceIoControl` with
  `FSCTL_SET_SPARSE` and `FSCTL_QUERY_ALLOCATED_RANGES`, reads the physical size
  with `GetCompressedFileSizeW` and `GetFileInformationByHandleEx`, and shells
  out to `fsutil`. A value returned by the candidate package is never used as the
  reference for its own correctness.

  **This file ships twice.** Harbor copies `tests/` into the container at
  `C:\tests` for the verifier step, and `tests/run_tests.ps1` resolves the suite
  from there; the copy under `verifier/` is the delivered record of what was
  graded. The two copies must stay byte-identical -- their SHA-256 was
  `a51e434b056d527474860426401c636e0675377cbdaa5915e6353cb13b5cd4a4` when this
  revision was sealed. A mismatch means the graded suite is not the recorded one.
- `oracle/reference/wsparse/` -- the reference payload. `oracle/solve.ps1`
  installs it over the candidate package for the Golden control.
- `rubric.conditions.json` -- the machine-readable conditions behind
  `tests/rubric.json`.
- `ISOLATION.md` -- how the boundary is enforced and re-checked.
- `negative_access_probe.ps1` -- proves the boundary from inside a container.
- `evidence/verifier-run/` -- the captured control run.

## Windows/NTFS mechanism anchors

`metadata/windows_mechanism.json` records the counterfactual, the exclusive
declaration, the five mechanism anchors (each bound to a verbatim clause of
`instruction.md`, a `test_ref` into the hidden suite and one F2P case) and the
environment-layer anchor that makes a volume without sparse-file support fail the
readiness probe instead of silently grading the candidate.

## Why no sparse sample is shipped

Sparse-ness is a property of the on-disk layout rather than of the byte content,
and it does not survive a copy: a sparse file that travels through a zip archive,
a build context or a container layer arrives fully materialised. This was
measured on this very image -- an earlier revision generated the samples during
the build and the layer carrying them failed to commit with
`hcsshim::ImportLayer failed in Win32: The system cannot find the path specified`.
So the workspace ships one dense control sample only, and the evaluator creates
every sparse fixture it measures on its own handle -- which is also what makes
the verdict independent of the candidate.
