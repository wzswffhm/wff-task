# Feishu requirements document

Authoritative source:

- URL: `https://vcnuhsx1gwu0.feishu.cn/wiki/BX1zwQR3kiohuakp3BccxTNdnMc`
- Document ID observed on 2026-10-02: `W7Jjdz8WAoDKl6xiPcvcRdmdnWf`
- Revision observed on 2026-10-02: `1`
- Title: `Outside Harbor Windows 题包格式培训 Demo`

Fetch the live document with `lark-cli docs +fetch --as user` before each new task. This reference is a routing summary, not a substitute for the live document.

## Complete local task structure

The requirements document defines this standard task package:

```text
<task-dir>/
├── task.toml
├── source.json
├── instruction.md
├── environment/
│   ├── adapter.toml
│   ├── Dockerfile
│   ├── prepare.ps1
│   ├── validate_environment.ps1
│   ├── run.ps1
│   ├── restore.ps1
│   ├── cleanup.ps1
│   └── workspace/                 # when needed
├── tests/
│   ├── test.ps1                  # generated; do not hand-edit or format
│   ├── run_tests.ps1
│   ├── aggregate_results.ps1
│   ├── judge.toml
│   ├── rubric.json
│   ├── run_matrix.ps1            # optional
│   ├── *_probe.ps1               # optional
│   └── fixtures/                 # optional
└── solution/
    ├── README.md
    ├── solve.ps1
    ├── solve.bat                 # optional
    └── reference.patch           # optional
```

The document also allows environment extensions for administrator overlays, scorer images, Compose services, offline assets, calibration, and dependency locks when genuinely needed.

## File contracts

- `task.toml`: immutable Docker image, task ID, author, tags, difficulty, agent/verifier/environment timeouts, CPU, and memory. The task directory, external record, and task ID must agree.
- `source.json`: real source type, source document/repository, commit, issue or PR, license, time, lineage, pollution risk, and authorization. Do not include private machine paths, accounts, secrets, or context-leaking URLs.
- `instruction.md`: background, goal, observable required behavior, boundaries, run entry, and user-visible acceptance. Do not include solution pseudocode, hidden assertions, or Golden details.
- `environment/run.ps1`: call prepare exactly once, invoke the real test path, and propagate accurate exit codes. Use `Join-Path`; default results to `results/result.json`.
- `environment/prepare.ps1`: validate prerequisites, clean transient state, create fixed fixtures, and preserve failures. Never modify the candidate implementation.
- `environment/cleanup.ps1`: idempotently remove task-created temporary data, build output, processes, registry/task/service state, and evaluator roots.
- `tests/rubric.json`: authoritative programmatic scoring with stable rubric IDs, weights, exact test IDs, evidence sources, pass conditions, and failure reasons.
- `tests/judge.toml`: bind to `rubric.json`, include its exact SHA-256, and keep programmatic weight at 1.0 with LLM judge weight at 0.0 unless the live requirements change.
- `tests/test.ps1`: stable generated entrypoint that delegates assertions and scoring and returns the real test exit code.
- `solution/**`: hidden, idempotent Golden implementation used only to prove solvability. Never include it in ordinary model assets.

## Writing and implementation rules

- Use UTF-8 consistently with the surrounding repository.
- Use `Join-Path` for Windows path composition.
- Add comments only for non-obvious purpose, platform constraints, invariants, or history.
- Mark generated files with a visible `Generated ... Do not edit.` notice and identify their source.
- Do not claim unverified network isolation, administrator capability, or compute results.
- Keep one authoritative expression for each intent; instruction, environment, tests, and rubric must describe the same behavior contract.

## Release checks

Before model runs and again before packaging, verify:

- directory, `task.toml`, `source.json`, rubric, and external record task IDs agree;
- task versions agree where task-version fields exist;
- participant-visible text contains only necessary information and no answer leakage;
- every rubric maps to concrete test IDs and machine-readable evidence;
- platform constraints such as offline execution, non-admin behavior, or Windows security semantics are explicit when applicable;
- `tests/test.ps1` launches from the task directory and returns the correct exit code;
- cleanup leaves no task-created residual state;
- `solution/**` is absent from ordinary model assets and the submission ZIP.

## Current delivery-scope override

The user's current submission request is only the Harbor four-piece ZIP: `task.toml`, `instruction.md`, `environment/`, and `tests/`. This is an output-scope restriction only. Continue to create and validate `source.json` and `solution/**` locally as required by the authoritative document, but exclude them from the current ZIP.
