# Isolation -- wfflab__wciocp-220

The candidate may only change `wciocp/` inside the workspace (`task.toml`,
`[policy] mutable_paths`). Everything that decides its score lives outside the
container image.

## What the agent container contains

`environment/Dockerfile` copies exactly one tree into the image:

```
COPY ["workspace/", "C:/testbed/"]
```

So the agent sees `C:\testbed` with `wciocp/`, `docs/` and `tests/` (the visible
smoke suite). Nothing else from the package is copied. In particular no
generator, no oracle payload and no hidden-suite file is ever placed in the
image.

## What is withheld

| path | why |
|---|---|
| `C:\verifier` | hidden behavioural suite and rubric conditions |
| `C:\solution` | oracle reference payload, injected only for the Golden control |
| `C:\tests` | the hidden suite as staged for the verifier step of scoring |
| `C:\task\verifier`, `C:\task\tests` | the scoring chain (`run_tests.ps1`, `test.ps1`, `aggregate_results.ps1`, `rubric.json`, the hidden suite) |
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
   container: its default list is `C:\verifier`, `C:\solution`, `C:\task\verifier`,
   `C:\task\solution`, `C:\task\tests`, `C:\tests` and
   `C:\testbed\tests\test_wciocp_semantics.py`, plus a scan of `C:\testbed` for
   withheld material. Exit 0 means the boundary held; exit 1 means something the
   candidate must not see is reachable.
4. `environment/agent_visible_paths.json` carries the machine-readable list and
   the evidence strings behind it.

## The three-layer lock

* the prompt names the mechanism in verifiable behaviour (`instruction.md`,
  acceptance A-G, plus the explicit platform scope statement);
* the environment probes the real completion capability
  (`validate_environment.ps1` asserts the host is a Windows kernel, that a
  completion port can be created and a named pipe bound to it, that a pending
  read delivers a packet carrying the registered key and the right byte count,
  and that an empty wait reports `WAIT_TIMEOUT` (258));
* the evaluator holds its own kernel objects and observes the candidate from
  outside (`verifier/tests/test_wciocp_semantics.py` creates its own named pipes
  and overlapped client ends with `CreateNamedPipeW` / `CreateFileW`, registers
  each handle with its own completion key, issues its own pending reads through
  the candidate's `submit`, draws packets from four threads at once, and decides
  each request from what the kernel handed back -- every submitted read must come
  back exactly once, carrying the key that was registered for its handle, and a
  pool closed while a read is outstanding must hand that read back with
  `status == "cancelled"`).

## Scope note: no handle-inheritance or process handover surface

Contrast only -- none of this appears in the delivered docs or in the solution.
This task does not involve process creation or handle handover: the solution
never needs `subprocess`/`spawn`, never needs a child process, and never needs an
inherit bit, `STARTUPINFOEX`, or a `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`; those
belong to a different task family. Every measurement above is taken inside one
process: the suite creates its own kernel objects, posts its own overlapped reads
and drains the port from several threads. Nothing about the boundary depends on
what crosses a process boundary, because nothing is supposed to cross one.

The boundary holds for one further reason: the contract itself is Windows-only.
It is defined by the kernel keeping a handle's completion key and handing it back
inside the completion packet, and by the port's queue deciding which waiting
thread gets a packet. Scope statement, verbatim: the contract only exists on a real Windows kernel; POSIX epoll/kqueue and io_uring model completion differently and are not an equivalent implementation. A host that is not a real
Windows kernel therefore fails the readiness probe outright rather than grading
the candidate on a lookalike contract.
