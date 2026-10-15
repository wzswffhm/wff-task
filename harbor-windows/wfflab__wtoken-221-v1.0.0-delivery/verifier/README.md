# Verifier side -- wfflab__wtoken-221

This directory never enters the agent container. It carries:

- `tests/test_wtoken_semantics.py` -- the hidden behavioural suite. Every
  assertion is backed by a measurement the suite performs itself: it opens the
  process token with `OpenProcessToken`, reads the privilege array with
  `GetTokenInformation(TokenPrivileges)`, resolves names and identifiers with
  `LookupPrivilegeName` / `LookupPrivilegeValue`, switches the enabled bit
  **through the candidate's** `set_privilege` and then re-reads the attributes
  word on its own handle, and compares elevation and the mandatory label against
  `TokenElevation` / `TokenElevationType` / `TokenIntegrityLevel`. A value
  returned by the candidate is never used as the reference for its own
  correctness.

  **This file ships twice.** Harbor copies `tests/` into the container at
  `C:\tests` for the verifier step, and `tests/run_tests.ps1` resolves the suite
  from there; the copy under `verifier/` is the delivered record of what was
  graded. The two copies must stay byte-identical -- a mismatch means the graded
  suite is not the recorded one.
- `oracle/reference/wtoken/` -- the reference payload. `oracle/solve.ps1`
  installs it over the candidate package for the Golden control.
- `rubric.conditions.json` -- the machine-readable conditions behind
  `tests/rubric.json`.
- `ISOLATION.md` -- how the boundary is enforced and re-checked.
- `negative_access_probe.ps1` -- proves the boundary from inside a container.

## Windows token mechanism anchors

`metadata/windows_mechanism.json` records the counterfactual, the exclusive
declaration, six mechanism anchors (each bound to a verbatim clause of
`instruction.md`, a `test_ref` into the hidden suite and one F2P case) and the
environment-layer anchor that makes a host without the required token capability
fail the readiness probe instead of silently grading the candidate.

The fact the whole task rests on, measured in the pinned image:

* a token carries a privilege array in which each entry pairs a LUID with an
  attributes word, and a privilege can be **present in that array while its
  enabled bit is clear** -- so "it appeared in the list" and "it is switched on"
  are two different answers to two different questions;
* the enabled bit is written only through `AdjustTokenPrivileges` and is visible
  to every other reader of the same token, which is what lets the evaluator check
  the change without trusting the candidate;
* POSIX models authority as a user id plus supplementary groups, with no
  per-privilege record that can be held-but-off, so the distinguishing point of
  this task cannot be expressed on that platform at all.
