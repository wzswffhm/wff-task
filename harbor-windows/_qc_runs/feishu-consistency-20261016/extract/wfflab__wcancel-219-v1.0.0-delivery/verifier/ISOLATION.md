# Isolation -- wfflab__wcancel-219

The candidate may only change `wcancel/` inside the workspace. Everything that
decides its score lives outside the container image.

## What the agent container contains

`environment/Dockerfile` copies exactly one tree into the image:

```
COPY ["workspace/", "C:/testbed/"]
```

So the agent sees `C:\testbed` with `wcancel/`, `docs/` and `tests/`. Nothing else
from the package is copied. In particular no generator, no oracle payload and no
hidden-suite file is ever placed in the image.

## What is withheld

| path | why |
|---|---|
| `C:\verifier` | hidden behavioural suite and rubric conditions |
| `C:\solution` | oracle reference payload, injected only for the Golden control |
| `C:\tests`, `C:\task\tests` | the scoring chain (`run_tests.ps1`, `test.ps1`, `aggregate_results.ps1`, `rubric.json`) |
| `C:\task\solution` | golden entry points |
| any oracle patch | this package ships none: the Oracle control installs the reference payload directly, it is never applied as a patch to the candidate |

## How it is re-checked

1. `environment/validate_environment.ps1` fails the readiness probe when any file
   under the workspace matches `oracle|golden|reference|hidden|rubric|solution|reward`,
   and when `C:\verifier` or `C:\solution` resolves inside the workspace. A
   non-zero exit there means the environment is INVALID, never that the candidate
   scored 0.
2. `tests/run_tests.ps1` returns exit code 2 -- INVALID -- when the candidate
   package is missing, when the verifier-side hidden suite was not injected, or
   when any required case came back with a non-terminal status.
3. `verifier/negative_access_probe.ps1` proves the boundary from inside a running
   container.
4. `environment/agent_visible_paths.json` carries the machine-readable list and
   the evidence strings behind it.

## The three-layer lock

* the prompt names the mechanism in verifiable behaviour (`instruction.md`,
  acceptance A-G, plus the explicit platform scope statement);
* the environment probes the real object's cancellation capability
  (`validate_environment.ps1` asserts the host is a Windows kernel, that a named
  pipe can be opened with `FILE_FLAG_OVERLAPPED`, that an empty read on it comes
  back as `997 ERROR_IO_PENDING`, and that cancelling that one request surfaces as
  `995 ERROR_OPERATION_ABORTED`);
* the evaluator holds its own kernel objects and observes the candidate from
  outside (`verifier/tests/test_wcancel_semantics.py` creates its own named pipe
  and overlapped client end with `CreateNamedPipeW` / `CreateFileW`, issues its
  own pending reads through the candidate's `submit`, cancels from a second
  thread, and decides each request's outcome from the kernel's terminal state --
  `995 ERROR_OPERATION_ABORTED` for the aborted request, `996
  ERROR_IO_INCOMPLETE` for a neighbour that must still be outstanding, and a
  normal completion carrying the written bytes for a request that was never
  cancelled).

## Scope note: no handle-inheritance or process handover surface

Contrast only -- none of this appears in the delivered docs or in the solution.
This task does not involve process creation or handle handover: the solution never
needs `subprocess`/`spawn`, never needs a child process, and never needs an
inherit bit, `STARTUPINFOEX`, or a `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`; those
belong to a different task family. Every measurement above is taken inside one
process: the suite creates its own kernel objects, posts its own overlapped reads,
cancels from a second thread and reads the terminal state back. Nothing about the
boundary depends on what crosses a process boundary, because nothing is supposed
to cross one.

The boundary holds for one further reason: the contract itself is Windows-only.
It is defined by `CancelIoEx` naming a single `OVERLAPPED` and by
`GetOverlappedResult` reporting `995`/`996`/`1168`; POSIX `aio_cancel` and
`io_uring` model cancellation differently and are not an equivalent
implementation. A host that is not a real Windows kernel therefore fails the
readiness probe outright rather than grading the candidate on a lookalike
contract.
