# Trae Runner Contract

## Fixed installation

- Source: `https://github.com/bytedance/trae-agent`
- Commit: `e839e559ac61bdd0e057c375dd1dee391fee797d`
- Package / CLI version: `trae-agent 0.1.0` / `trae-cli 0.1.0`
- Python: `3.12.13`
- Windows executable: `C:\Users\Administrator\.local\bin\trae-cli.exe`
- Provider / model ID: `doubao` / `doubao-seed-evolving`
- Agent Plan base URL: `https://ark.cn-beijing.volces.com/api/plan/v3/`
- Compatibility image: `obm-trae-runner:0.1.0-e839e559-jsonrepair4`. It retains the fixed upstream source and adds `json-repair==0.63.4` only for malformed tool-call argument JSON; valid JSON stays on the original `json.loads` path. It also filters edit-tool arguments by CLI sub-command and shell-quotes values, because upstream Docker execution otherwise forwards irrelevant optional fields and rejects valid edits. The image copies the packaged edit binaries into the installed `trae_agent/dist` path and includes Git because Trae evaluates `--must-patch` from the runner. Record the patch metadata, probe hashes, and image ID in every run manifest.

The pinned package declares `docker` and `pexpect` only in its `evaluation` extra but imports both on the ordinary CLI startup path. Install them in the same isolated tool environment. The verified Windows installation command is:

```powershell
uv tool install --force `
  --with 'docker>=7.1.0' `
  --with 'pexpect>=4.9.0' `
  'git+https://github.com/bytedance/trae-agent.git@e839e559ac61bdd0e057c375dd1dee391fee797d' `
  --python 3.12
```

Verify with `trae-cli --version`, `trae-cli --help`, and `trae-cli run --help`. Do not substitute the unrelated npm package or the Trae desktop IDE.

## Secret-free configuration

Keep the checked-in/cache YAML free of credentials. `model_providers.doubao.api_key` may be an empty string because Trae resolves `DOUBAO_API_KEY` from the process environment at run time. This batch uses the Agent Plan base URL `https://ark.cn-beijing.volces.com/api/plan/v3/`. The key and exact `doubao-seed-evolving` model ID were verified with a minimal request returning HTTP 200. The local credential is protected with Windows DPAPI and is injected only by `scripts/invoke-trae-with-ark-key.ps1`; do not substitute the standard `/api/v3/` endpoint or the `ark-code-latest` alias in scoring evidence.

Never pass a real key value via `--api-key`: command lines can be captured in process listings and logs. Pass only the environment-variable name into the runner with Docker's `--env DOUBAO_API_KEY` form. Do not save `show-config` output from a credentialed process; it reveals the first and last four key characters. Do not place a `.env` file below `D:\hc\obm`.

On this machine, invoke Trae through the DPAPI wrapper and pass every Trae CLI token in the explicit array:

```powershell
& .\scripts\invoke-trae-with-ark-key.ps1 -TraeArguments @('run', '--config', '<config-path>', '<other-args>')
```

Do not pass free positional arguments to the wrapper; `-SecretFile` and `-TraeExecutable` are named maintenance overrides only.

Disable Lakeview for scoring so the run does not introduce a second summarizer model. Use the same model configuration and `max_steps: 120` for no-skill and with-skill. Trae exposes no random seed option in this version; record that fact instead of inventing one.

## Isolation

Run Trae itself in Linux. The Windows executable is suitable for installation and CLI/schema verification, but not for formal Linux scoring:

- The installed Docker manager uses Unix `pexpect.spawn` to open `docker exec -it ... /bin/bash`.
- Docker mode does not set `network_mode=none` when it creates a container.
- Windows `pexpect 4.9.0` has no `spawn` implementation.

The verified local arrangement uses Docker Desktop's `desktop-linux` context, runner image `obm-trae-runner:0.1.0-e839e559-jsonrepair4`, and task image `obm-task-python-git:3.12-v2`. The runner mounts the Docker socket. First start a separate Linux task container outside Trae with the frozen app mounted at `/workspace`, working directory `/workspace`, the declared CPU/memory/storage limits, and `--network none`. Initialize and commit the exact frozen workspace as a clean Git baseline before Trae starts. Then invoke Trae in the runner image with `--docker-container-id <id>`. This keeps Doubao API traffic in the Linux runner while tool execution remains in the offline task container. Record `docker inspect` output as evidence and remove both the task container and any interrupted runner container after evidence collection, since interrupting the host `docker run --rm` client may leave the runner alive.

Before any paid model request, assert that Git exists in both images, the runner can read the task-created baseline commit through the bind mount, the repository is clean, and `/agent_tools/edit_tool` plus `/agent_tools/json_edit_tool` are executable. A disposable attach/copy smoke test must demonstrate that Trae's `DockerManager` copies the installed package tools successfully.

Do not use `--dockerfile-path` with this candidate: this Trae version treats the Dockerfile's own directory as build context, while the candidate Dockerfile expects `sources` as its context.

## Paired runs

Freeze and hash the proposal and sources before either run. If the user requested a separate approval, wait for it. Prepare two new workspace copies from the same frozen baseline and use separate containers and Trae processes.

- no-skill task input is the exact frozen `sources/instruction.md` text.
- with-skill task input is the same text plus only the frozen `proposal.expert_experience_skill`, clearly delimited.
- Do not expose the proposal's verifier prose, reference patch, verifier implementation, the other run's workspace, or its trajectory.
- Write console logs, trajectory JSON, patch output, workspace hash, container inspection, and later verifier output under the candidate `evidence` directory.

Use non-interactive `trae-cli run` with `--file`, `--config-file`, `--max-steps 120`, `--working-dir`, `--trajectory-file`, `--patch-path`, `--docker-container-id`, and `--console-type simple`. Preserve the CLI exit code. A zero exit code or trajectory `success: true` is not a quality PASS.

## Metrics and quality-incentive targets

Count turns as `len(agent_steps)` and cross-check `len(llm_interactions)`. Use root `execution_time` for duration. Run `scripts/summarize-trae-trajectory.ps1` to create the factual summary; it deliberately leaves verifier status unevaluated.

- A no-skill verifier PASS at 100 turns or fewer means the item-2 task-value target is not met. It does not reject a candidate that already passes data-quality item 1.
- A no-skill verifier failure with fewer than 100 recorded turns is inconclusive for item 2.
- A no-skill failure after at least 100 turns plus a with-skill verifier PASS satisfies the main item-2 improvement branch.
- If both pass, no-skill must take more than 100 turns and with-skill should reduce turns or duration by at least 30%; 50% is the target.

These metrics determine only the internal quality-incentive status. Record `met`, `not_met`, `inconclusive`, or `not_run` truthfully. They must not block packaging or Feishu submission when the static/content acceptance requirements in data-quality item 1 have passed.

Only the independent verifier determines solved status. Keep Trae's agent-reported success as a separate field.
