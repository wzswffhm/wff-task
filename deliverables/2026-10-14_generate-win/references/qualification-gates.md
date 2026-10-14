# Qualification gates

Use a qualification epoch timestamp immediately after the last material task/verifier/environment change. Only results created after that timestamp may enter the official set.

## Controls

- Structural validation: pass.
- NOP/no-change: three independent runs; each raw `result.json` must have `test.report.status = VALID` and top-level `verdict = 0`.
- Oracle/Golden: three independent runs; each raw `result.json` must have `test.report.status = VALID` and top-level `verdict = 1`.
- A screenshot or aggregate summary never replaces the raw result, verifier/test log, task identity, task version, and qualification-epoch evidence.

An `INVALID` control indicates infrastructure, runner, setup, timeout, or verifier failure. Repair it; do not count it as `0`.

The complete local task must follow the requirements/demo tree: `task.toml`, `source.json`, `instruction.md`, the seven standard `environment/**` files plus `workspace/` when needed, the standard `tests/**` entrypoints, and hidden `solution/README.md` plus `solution/solve.ps1`. The minimal `tasks/demo-windows-path` smoke-test tree is not sufficient.

## Model matrix

Official valid scored runs:

| Model | Count |
| --- | ---: |
| QWEN | 3 |
| OPUS | 3 |
| GLM | 1 |
| KIMI | 1 |

The differentiation gate is:

```text
sum(OPUS scores) > sum(QWEN scores)
```

Both `0` and `1` are valid candidate outcomes when verification completed normally. Provider/authentication/gateway failures and verifier-infrastructure failures are not valid scores and must be retried.

## Repair semantics

- A provider/configuration repair may rerun only missing model attempts.
- A task instruction, workspace, environment, test, rubric, judge, or Golden change invalidates prior controls and model scores. Start a new epoch and rerun the full set.
- Avoid tuning tests to one model's patch. Verify behavior, compatibility, and relevant regression constraints.
- Use no more than three full material-remediation cycles by default. Report a precise blocker after that ceiling.

## Evidence

Select result files deterministically and record their run IDs, task version, verdict, duration, agent status, and verifier-log hash when available. Screenshots and summaries must be generated from these files.
