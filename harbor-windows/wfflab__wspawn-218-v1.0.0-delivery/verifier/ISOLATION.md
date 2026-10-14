# Isolation -- wfflab__wspawn-218

The candidate may only change `wspawn/` inside the workspace. Everything that
decides its score lives outside the container image.

## What the agent container contains

`environment/Dockerfile` copies exactly one tree into the image:

```
COPY ["workspace/", "C:/testbed/"]
```

So the agent sees `C:\testbed` with `wspawn/`, `docs/` and `tests/`. Nothing else
from the package is copied. In particular no generator, no oracle payload and no
hidden-suite file is ever placed in the image.

## What is withheld

| path | why |
|---|---|
| `C:\verifier` | hidden behavioural suite and rubric conditions |
| `C:\solution` | oracle reference payload, injected only for the Golden control |
| `C:\tests`, `C:\task\tests` | the scoring chain (`run_tests.ps1`, `test.ps1`, `aggregate_results.ps1`, `rubric.json`) |
| `C:\task\solution` | golden entry points |
| `oracle.patch` | ships outside the agent-visible package |

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
* the environment probes the real object's capability
  (`validate_environment.ps1` asserts the host is a Windows kernel, that the
  process can create an inheritable pipe and read its flag back, and that it can
  start a child process);
* the evaluator holds its own kernel objects and observes the candidate from
  outside (`verifier/tests/test_wspawn_semantics.py` creates its own pipes, reads
  their inherit flags with `GetHandleInformation`, launches a child through the
  candidate and asks that child which handles it could actually use).
