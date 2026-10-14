# Standard Task delivery

Use this mode only when QC, review, or the recipient explicitly requests a complete standard Task package. The current default delivery mode is the Harbor four-piece package.

## Required shape

```text
<task-id>/
├── task.toml
├── source.json
├── instruction.md
├── environment/
├── tests/
├── solution/
├── outside_harbor/
│   └── import.json
└── delivery-extras/
    ├── source/
    ├── hashes/
    │   └── manifest.sha256
    ├── original-runs/
    ├── model_runs/
    └── evidence/
```

The `environment/` tree must include `adapter.toml`, `Dockerfile`, `prepare.ps1`, `validate_environment.ps1`, `run.ps1`, `restore.ps1`, and `cleanup.ps1`. The `tests/` tree must include `test.ps1`, `run_tests.ps1`, `aggregate_results.ps1`, `judge.toml`, and `rubric.json`. The complete local task must also include `source.json` and `solution/**` before any packaging step.

## Evidence closure

`outside_harbor/import.json` is an import manifest, not a score summary. It must identify the task ID/version, participant entrypoint, verifier entrypoint, source commit, rubric, and every file included in the standard package.

`delivery-extras/source/` must preserve source provenance and lineage without private machine paths or secrets. `delivery-extras/hashes/manifest.sha256` must be generated after staging and cover the staged package. `delivery-extras/model_runs/` must include the qualification summary and one compact record for every selected no-change, Golden, Qwen, Opus, GLM, and Kimi result. `delivery-extras/original-runs/` must include the corresponding raw `result.json` and verifier/test logs, keyed by run ID. Include agent event traces only when the recipient requires them and after checking them for secrets.

The evidence must be generated from actual files. Do not recreate scores or run IDs from memory, and do not treat screenshots as a replacement for raw records.

## Safety and reproducibility

- Reject the package if any required run is missing, invalid, from another task version, or not covered by the qualification summary.
- Reject `.env.local`, API keys, OAuth state, credentials, private source paths, source caches, workspaces copied from run directories, build output, and unrelated runs.
- Normalize local paths in manifests to package-relative paths.
- Keep `solution/**` in the standard package for QC/Golden verification; omit it only from a separately derived public four-piece package.
- Re-extract the ZIP and validate the staged shape before upload.

## Relationship to the Harbor four-piece package

The four-piece ZIP is a derived participant package containing only `task.toml`, `instruction.md`, `environment/`, and `tests/`. It is useful for public task distribution but does not prove source lineage, Golden correctness, model qualification, or execution provenance. Never submit it alone when the recipient's checklist asks for a standard Task, `outside_harbor` import data, or `delivery-extras`.
