# Harbor four-piece rules

Use this reference while creating, repairing, or packaging a task.

## Complete local task versus public deliverable

The Feishu requirements document defines a complete local task containing `source.json` and hidden `solution/**` in addition to the participant-facing files. Create and validate that complete local structure first.

The Harbor four-piece ZIP is the current default participant/public package. Its narrow scope does not make `source.json` or `solution/**` optional in the complete local task. A standard Task package with `outside_harbor/` and `delivery-extras/` is built only when explicitly requested.

## Public deliverable

The submission ZIP contains one task root and exactly these top-level components:

1. `task.toml`
2. `instruction.md`
3. `environment/`
4. `tests/`

`solution/` may exist locally for Golden validation but is hidden and must never be submitted.

`source.json` must exist and pass provenance validation in the complete local task, but is excluded from the current four-piece ZIP because the user explicitly limited the upload scope. Include it only if the user or live delivery specification later expands the submission scope.

When a recipient's checklist mentions a standard Task, `outside_harbor`, delivery extras, source lineage, hashes, original runs, or model runs, stop using this four-piece ZIP as the sole deliverable. Read [standard-delivery.md](standard-delivery.md) and build the standard package instead.

## Content rules

- Keep the task ID consistent across the directory name, `task.toml`, rubric, judge configuration, result schema, and external record.
- Keep the complete local task's `source.json` task ID/version consistent with those same records.
- Use a requirements-compatible `task.toml` with immutable `docker_image`, metadata, agent/verifier timeouts, environment resources, and the local runner compatibility sections.
- Pin source/repository state to an immutable commit or frozen asset.
- Keep `instruction.md` participant-facing. State observable behavior and constraints without leaking hidden assertions or the reference patch.
- Make `tests/**` the objective source of truth. Emit machine-readable results and preserve the distinction between functional failure and infrastructure failure.
- Make `environment/**` include `adapter.toml`, `Dockerfile`, `prepare.ps1`, `validate_environment.ps1`, `run.ps1`, `restore.ps1`, and `cleanup.ps1`. `run.ps1` prepares once, executes verification, and propagates exit codes. `cleanup.ps1` is real, safe, and idempotent.
- Keep `rubric.json` authoritative. Bind `judge.toml` to the rubric and update its SHA-256 after changing the rubric.
- Include `test.ps1`, `run_tests.ps1`, and `aggregate_results.ps1`. Keep `test.ps1` machine-generated, visibly marked, and unedited.
- Mark every machine-generated file when appropriate.

## Forbidden package content

Do not include any of the following:

- `solution/`, `evidence/`, `results/`, `runs/`, `output/`, or local working notes
- `.env.local`, API keys, access tokens, OAuth state, credentials, or private paths
- model prompts/responses, agent traces, provider logs, or score-selection notes
- `.git/`, source caches, package caches, temporary directories, or downloaded installers
- `bin/`, `obj/`, `TestResults/`, `.nuget-packages/`, `node_modules/`, `__pycache__/`
- editor state, crash dumps, `.DS_Store`, `Thumbs.db`, `*.user`, `*.suo`, or transient logs

## Fresh-extraction check

Before creating the ZIP, run `scripts/validate_requirement_conformance.py` against the complete local task. Then extract the ZIP into a new temporary directory, confirm the exact four-piece top-level shape, rerun the package-compatible structural validation against the extracted task, and compare the packaged task ID/version with the screenshots and Feishu record.
