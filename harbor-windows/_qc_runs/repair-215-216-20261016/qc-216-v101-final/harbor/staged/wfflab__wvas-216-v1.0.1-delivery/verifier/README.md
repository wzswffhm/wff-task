# Verifier side -- wfflab__wvas-216

This directory never enters the agent container. It carries:

- `tests/test_wvas_semantics.py` -- the hidden behavioural suite. Every
  assertion is backed by a measurement the suite performs itself: it starts a
  target process, records the mappings that process created for it (a file
  mapping backed by a sample file, an anonymous mapping, a private committed
  allocation and a 6 GiB reservation), then walks that process with its own
  `VirtualQueryEx` calls, names its file-backed regions with its own
  `GetMappedFileNameW` calls and translates the device paths with its own
  `QueryDosDeviceW` calls. A value returned by the candidate package is never
  used as the reference for its own correctness.

  **This file ships twice.** Harbor copies `tests/` into the container at
  `C:\tests` for the verifier step, and `tests/run_tests.ps1` resolves the suite
  from there; the copy under `verifier/` is the delivered record of what was
  graded. The two copies must stay byte-identical -- their SHA-256 is
  `bfe41f7d53dc5b2674dfa02723cdcd25d3b61ff649e0b2d0c4d061c668f0564e` for this
  revision. A mismatch means the graded suite is not the recorded one.
- `oracle/reference/wvas/` -- the reference payload. `oracle/solve.ps1` installs
  it over the candidate package for the Golden control.
- `rubric.conditions.json` -- the machine-readable conditions behind
  `tests/rubric.json`.
- `ISOLATION.md` -- how the boundary is enforced and re-checked.
- `negative_access_probe.ps1` -- proves the boundary from inside a container.

## Why the suite measures its own process

The addresses a process uses are decided at run time by the loader and the ASLR
seed, so no captured snapshot can serve as the answer key: a snapshot taken on
one machine is wrong on the next, and a snapshot taken inside the image would
still be wrong after the target has been started. The suite therefore creates
the situation it grades -- it starts a target process whose mappings it chose,
waits until that process reports them, and only then asks the candidate.

## Why the image inventory does not come from the region walk

Inside a Windows container the images the loader maps do not come from a mounted
volume: they arrive through a VSMB share, and `GetMappedFileNameW` names them
`\Device\vmsmb\VSMB-{...}\{...}\Files\...`. No DOS device carries that prefix,
so those names cannot be turned into a path a user can open -- while the very
same files are reachable as `C:\...` from inside the container. The measured
consequence on the delivered image was that a region walk could not name a
single image, and an inventory derived from that walk came back empty.

The suite therefore grades `modules()` on its own surface: the inventory has to
be complete and duplicate-free even where the region walk cannot name a region,
and the contract only asks the region walk to name what it can name (a region
whose backing file cannot be expressed as an openable path is reported with
`path = None`). `instruction.md` states this explicitly, so the contract stays
solvable inside the container.

## Windows mechanism anchors

`metadata/windows_mechanism.json` records the counterfactual, the exclusive
declaration, the eight mechanism anchors (each bound to a verbatim clause of
`instruction.md`, a `test_ref` into the hidden suite and one F2P case) and the
environment-layer anchor that makes a non-Windows host fail the readiness probe
instead of silently grading the candidate.
