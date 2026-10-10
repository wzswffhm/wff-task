#!/usr/bin/env python3
"""Local Outside Harbor Windows runner.

Executes a generated Windows task against Docker Desktop running Windows
containers, and writes the run artifacts in the layout the qualification
scripts expect:

    <workspace-root>/runs/<task_id>/<run_id>/<label>/result.json
    <workspace-root>/runs/<task_id>/<run_id>/<label>/test.log
    <workspace-root>/runs/<task_id>/<run_id>/<label>/checks.json
    <workspace-root>/runs/<task_id>/<run_id>/<label>/agent.log

Modes
-----
no-change   run the verifier against the untouched workspace (NOP control)
golden      apply solution/solve.ps1, then run the verifier (Oracle control)
candidate   let a model edit the task's mutable sources, then verify

The candidate never sees tests/ or solution/: the model works in a reduced view
of the task tree and the verifier is applied to a pristine copy afterwards.

Usage
-----
    python runner.py --task wfflab__wreparse-217 --mode no-change --runs 3
    python runner.py --task wfflab__wreparse-217 --mode golden --runs 3
    python runner.py --task wfflab__wreparse-217 --mode candidate --models QWEN --runs 3
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent
ALIASES = ("QWEN", "OPUS", "GLM", "KIMI")
CONTAINER_TASK_ROOT = "C:\\task"

# --------------------------------------------------------------------------- #
# task profile
#
# This harness used to hard-code wfflab__wreparse-217's module name, contract
# document, language persona and write whitelist. That silently made every
# other task unwinnable: the agent's write tool refused any path outside the
# wrong module directory, the graded sources were never touched, and every
# candidate scored a structural 0 that looked like a model failure (observed
# 2026-10-07 on wfflab__wfmt-215). The profile is now resolved from the task's
# own task.toml -- [policy].mutable_paths / read_only_paths and
# [metadata].tags -- and the defaults below still reproduce the original
# wreparse-217 behaviour exactly.
# --------------------------------------------------------------------------- #
LANGUAGE_PROFILES = {
    "powershell": {
        "persona": "a senior Windows/PowerShell engineer",
        "artifact_kind": "PowerShell module",
        "target_note": ("Target Windows PowerShell 5.1. No external modules or "
                        "packages. No network access."),
    },
    "python": {
        "persona": "a senior Python engineer",
        "artifact_kind": "Python package",
        "target_note": ("Target the CPython 3 standard library only. No third-party "
                        "packages. No network access."),
    },
}

DEFAULT_PROFILE = {
    "task_id": None,
    "language": "powershell",
    "module_rel": Path("environment") / "workspace" / "WReparse",
    "container_writable": "C:\\task\\environment\\workspace\\WReparse",
    "contract_docs": ["C:\\task\\environment\\workspace\\docs\\REPARSE-CONTRACT.md"],
    "samples_dir": None,
}

TASK_PROFILE: dict = dict(DEFAULT_PROFILE)

# Frozen once per invocation, then stamped into every run directory. The 118
# rework rejection was raised because job records could not be tied back to the
# task they were produced from, so each run now carries its own identity.
TASK_IDENTITY: dict = {}

# Binary fixtures are handed to the model as a hex dump. Cap the dump so one
# large sample cannot swallow the whole context window.
MAX_BINARY_DUMP_BYTES = 65536
# Agent step budget for a single attempt. Identical for every model.
#
# History. A 24-turn cap was trialled in round 7 as a differentiation lever and
# is now retired. Round 7 measured OPUS finishing naturally in 8 / 10 / 13 turns
# (untouched by the cap) while QWEN hit 24 turns twice -- and still scored 1.0
# both times, because 24 turns is enough for it to finish. The cap did not
# create differentiation, it only truncated a model that already saturates the
# checks. It also does not ship: the delivered four-piece zip carries no
# turn-budget field, so a receiver's harness cannot reproduce it. Do not use the
# budget as a differentiation lever; adjust the task surface instead.
#
# 80 is the neutral ceiling. Every natural finish observed on this task fits
# inside it -- OPUS 4/8/10/13/14/15/16/20/21/21/22/34/67 turns, QWEN
# 24/27/31/40/42/72 turns -- so the comparison measures contract fidelity
# rather than how quickly a model runs out of budget.
MAX_AGENT_TURNS = 80

PS_PREAMBLE = (
    "$ProgressPreference='SilentlyContinue';"
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
    "$OutputEncoding=[System.Text.Encoding]::UTF8;"
)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def resolve_image_tag(task_dir: Path) -> str:
    text = (task_dir / "task.toml").read_text(encoding="utf-8-sig")
    match = re.search(r'(?m)^\s*task_id\s*=\s*"([^"]+)"', text)
    task_id = match.group(1) if match else task_dir.name
    # [task].version, not the top-level platform schema version: the image tag has
    # to track the deliverable version that task_version reports.
    version = task_version_of(task_dir) or "1.0.0"
    return f"outside-harbor/{task_id}:{version}"


# --------------------------------------------------------------------------- #
# docker plumbing
# --------------------------------------------------------------------------- #
class DockerError(RuntimeError):
    pass


def docker(args: list[str], timeout: int | None = None, check: bool = False,
           stdin_text: str | None = None):
    try:
        proc = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            input=stdin_text,
        )
    except subprocess.TimeoutExpired as exc:
        raise DockerError(f"docker {' '.join(args[:2])} timed out after {timeout}s") from exc
    if check and proc.returncode != 0:
        raise DockerError(
            f"docker {' '.join(args[:3])} failed ({proc.returncode}): "
            f"{(proc.stderr or proc.stdout).strip()[:800]}"
        )
    return proc


def docker_ok() -> tuple[bool, str]:
    proc = docker(["version", "--format", "{{.Server.Os}}/{{.Server.Version}}"])
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, proc.stdout.strip()


def ensure_image(task_dir: Path) -> str:
    tag = resolve_image_tag(task_dir)
    if docker(["image", "inspect", tag]).returncode == 0:
        return tag
    log(f"building image {tag}")
    dockerfile = task_dir / "environment" / "Dockerfile"
    if not dockerfile.exists():
        raise DockerError(f"Dockerfile not found: {dockerfile}")
    proc = docker(
        ["build", "-t", tag, "-f", str(dockerfile), str(dockerfile.parent)],
        timeout=7200,
    )
    if proc.returncode != 0:
        raise DockerError(f"image build failed: {(proc.stderr or proc.stdout)[-2000:]}")
    return tag


# Run artefacts, not task content: they must never contribute to the task hash,
# both because they change on every run and because a receiver recomputes the
# hash from the delivered task tree alone.
TASK_HASH_SKIP_DIRS = {"jobs", "runs", "work", "results", "__pycache__",
                       ".pytest_cache", ".mypy_cache", ".git"}


def compute_task_hash(task_dir: Path) -> str:
    """sha256 over (relative path + sha256 of content) for every task file."""
    digest = hashlib.sha256()
    for path in sorted(p for p in task_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(task_dir)
        if any(part in TASK_HASH_SKIP_DIRS for part in rel.parts):
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(payload).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def task_version_of(task_dir: Path) -> str | None:
    """The task's own version, not the platform schema version.

    task.toml carries a top-level ``version = "1.0"`` (the Outside Harbor schema
    version) *and* ``[task].version`` (the deliverable version the platform
    tracks as task_version). Only the latter belongs in the identity record.
    """
    try:
        data = _load_toml(task_dir / "task.toml")
    except Exception:  # noqa: BLE001 - the manifest is advisory
        return None
    task = data.get("task") or {}
    metadata = data.get("metadata") or {}
    return task.get("version") or metadata.get("task_version") or data.get("version")


def build_task_identity(task_dir: Path, image: str) -> dict:
    proc = docker(["image", "inspect", image, "--format", "{{.Id}}"])
    image_digest = proc.stdout.strip() if proc.returncode == 0 else ""
    return {
        "task_id": TASK_PROFILE.get("task_id") or task_dir.name,
        "task_version": task_version_of(task_dir),
        "task_hash": compute_task_hash(task_dir),
        "task_hash_algorithm": (
            "sha256 over (relative posix path + sha256(file content)) for every file in the "
            "task tree, sorted by path; jobs/, runs/, work/, results/ and caches are excluded"),
        "docker_image": image,
        "docker_image_digest": image_digest,
        "captured_at": now_iso(),
    }


def capture_run_identity(run_dir: Path) -> None:
    """Write the task identity and the exact prompts fed to the model.

    Evidence capture must never abort a run, so every write is guarded.
    """
    try:
        (run_dir / "task_identity.json").write_text(
            json.dumps(TASK_IDENTITY, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - orchestration layer
        log(f"  !! task identity capture failed: {type(exc).__name__}: {exc}")
    for name, builder in (("prompt.system.txt", build_system_prompt),
                          ("prompt.task.txt", build_task_prompt)):
        try:
            (run_dir / name).write_text(builder(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - orchestration layer
            log(f"  !! {name} capture failed: {type(exc).__name__}: {exc}")


def wait_for_engine(max_wait: int = 900, poll: int = 10) -> bool:
    """Block until the Windows engine answers again.

    Docker Desktop's desktop backend can restart underneath a long batch -- the
    GUI process is effectively the engine's host, and if it goes away every
    docker call fails with a named-pipe error until it comes back. That is a
    transient outage, not a task failure, so wait it out instead of throwing
    away an entire run.
    """
    deadline = time.time() + max_wait
    while time.time() < deadline:
        ok, detail = docker_ok()
        if ok and detail.lower().startswith("windows"):
            return True
        time.sleep(poll)
    return False


def start_container(image: str, mount_dir: Path, name: str) -> None:
    docker(["rm", "-f", name])
    last_error = ""
    for attempt in range(1, 4):
        proc = docker([
            "run", "-d", "--name", name,
            "-v", f"{Path(mount_dir).resolve()}:{CONTAINER_TASK_ROOT}",
            image, "ping", "-t", "127.0.0.1",
        ])
        if proc.returncode == 0:
            break
        last_error = (proc.stderr or proc.stdout).strip()[:800]
        log(f"  !! container start attempt {attempt} failed: {last_error[:200]}")
        if attempt < 3:
            log("  waiting for the docker engine to come back ...")
            if wait_for_engine():
                log("  engine recovered; retrying container start")
            else:
                log("  engine still down after the wait window")
            docker(["rm", "-f", name])
    else:
        raise DockerError(f"container start failed: {last_error}")
    # wait until it is actually running
    for _ in range(60):
        state = docker(["inspect", "-f", "{{.State.Running}}", name]).stdout.strip()
        if state == "true":
            return
        time.sleep(1)
    raise DockerError("container did not reach the running state")


def stop_container(name: str) -> None:
    docker(["rm", "-f", name])


def ps_exec(container: str, script: str, timeout: int = 900):
    encoded = base64.b64encode((PS_PREAMBLE + script).encode("utf-16-le")).decode("ascii")
    return docker(
        ["exec", "-i", container, "powershell", "-NoProfile", "-ExecutionPolicy",
         "Bypass", "-NonInteractive", "-EncodedCommand", encoded],
        timeout=timeout,
    )


def ps_exec_file(container: str, script_path: str, timeout: int = 900, extra: str = ""):
    return ps_exec(container, f"& '{script_path}' {extra}", timeout=timeout)


# --------------------------------------------------------------------------- #
# task copies
# --------------------------------------------------------------------------- #
IGNORE_DIRS = {".git", ".fixture", "results", "runs", "__pycache__", ".venv", "work"}


def copy_tree(src: Path, dst: Path, skip: set[str] | None = None) -> None:
    skip = skip or set()
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns(*IGNORE_DIRS, *skip),
        dirs_exist_ok=False,
    )


def build_agent_view(case_dir: Path, view_dir: Path) -> None:
    """The candidate sees instruction.md and the mutable workspace only.

    Fixtures, runners and validators stay verifier-side. Handing the candidate
    the harness that builds the graded fixture turns the task into "align with
    this one fixture" instead of "implement the documented contract"; keeping
    it back is the usual SWE-bench split and makes the contract the sole
    authority.
    """
    if view_dir.exists():
        shutil.rmtree(view_dir, ignore_errors=True)
    view_dir.mkdir(parents=True)
    shutil.copy2(case_dir / "instruction.md", view_dir / "instruction.md")
    source = case_dir / "environment" / "workspace"
    target = view_dir / "environment" / "workspace"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source, target,
        ignore=shutil.ignore_patterns(*IGNORE_DIRS),
    )


def mirror_workspace(view_dir: Path, case_dir: Path) -> None:
    source = view_dir / TASK_PROFILE["module_rel"]
    target = case_dir / TASK_PROFILE["module_rel"]
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def workspace_fingerprint(view_dir: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    root = view_dir / TASK_PROFILE["module_rel"]
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# model client
# --------------------------------------------------------------------------- #
class ModelError(RuntimeError):
    pass


class ModelClient:
    def __init__(self, cfg: dict, log_path: Path | None):
        self.cfg = cfg
        self.log_path = log_path

    def _log(self, text: str) -> None:
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(text + "\n")

    def call(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        url = self.cfg["base_url"].rstrip("/") + "/v1/messages"
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            # The ebondai gateway blocks the default Python-urllib User-Agent
            # with HTTP 502 "Upstream access forbidden" (bot protection,
            # observed from 2026-10-06 ~21:50; browser/curl UAs pass). Set an
            # explicit browser UA for all models; domestic endpoints ignore it.
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }
        if self.cfg.get("auth", "x-api-key").lower() == "authorization":
            headers["authorization"] = "Bearer " + self.cfg["api_key"]
        else:
            headers["x-api-key"] = self.cfg["api_key"]

        body: dict = {
            "model": self.cfg["model"],
            "max_tokens": int(self.cfg.get("max_tokens", 16000)),
            "system": system,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools
        body.update(self.cfg.get("extra_body") or {})

        stream = bool(self.cfg.get("stream"))
        if stream:
            body["stream"] = True
            headers["accept"] = "text/event-stream"

        payload = json.dumps(body).encode("utf-8")
        timeout = int(self.cfg.get("request_timeout", 900))
        last_error = ""
        # Retry hardening (2026-10-06): the ebondai gateway shows intermittent
        # HTTP 502 "Upstream access forbidden" windows lasting ~0.5-2 min.
        # The old 3-attempt / 5s-step policy (~20s total) could never outlive
        # one, so a whole run died as agent_status=error. 7 attempts with a
        # cumulative ~5.75 min backoff rides out such windows. Scoring is
        # unaffected: agent errors are still excluded, this only saves re-runs.
        retry_delays = (15, 30, 60, 60, 90, 90)
        for attempt in range(1, len(retry_delays) + 2):
            request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    if stream:
                        return self._read_stream(response)
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:600]
                last_error = f"HTTP {exc.code}: {detail}"
            except Exception as exc:  # noqa: BLE001 - network layer
                last_error = f"{type(exc).__name__}: {exc}"
            self._log(f"!! model call attempt {attempt} failed: {last_error}")
            if attempt <= len(retry_delays):
                time.sleep(retry_delays[attempt - 1])
        raise ModelError(last_error)

    @staticmethod
    def _read_stream(response) -> dict:
        """Reassemble an Anthropic-style SSE stream into one response dict.

        The shape returned here is byte-for-byte compatible with the
        non-streaming JSON body, so the agent loop needs no changes:
        ``{"content": [...], "stop_reason": ..., "usage": {...}}``.

        ``tool_use`` inputs arrive as ``input_json_delta`` fragments that must
        be concatenated and parsed once the block closes; a truncated stream
        yields ``input={}`` so the tool layer reports a normal ERROR instead of
        crashing the run.
        """
        blocks: dict = {}
        stop_reason = None
        usage: dict = {}
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                event = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "message_start":
                message = event.get("message") or {}
                usage.update(message.get("usage") or {})
                stop_reason = message.get("stop_reason") or stop_reason
            elif kind == "content_block_start":
                blocks[event.get("index", 0)] = dict(event.get("content_block") or {})
            elif kind == "content_block_delta":
                delta = event.get("delta") or {}
                block = blocks.setdefault(event.get("index", 0), {"type": "text", "text": ""})
                dtype = delta.get("type")
                if dtype == "text_delta":
                    block["text"] = block.get("text", "") + (delta.get("text") or "")
                elif dtype == "input_json_delta":
                    block["_partial_json"] = block.get("_partial_json", "") + (
                        delta.get("partial_json") or ""
                    )
                elif dtype == "thinking_delta":
                    block["thinking"] = block.get("thinking", "") + (delta.get("thinking") or "")
            elif kind == "content_block_stop":
                block = blocks.get(event.get("index", 0))
                if block and block.get("type") == "tool_use":
                    partial = block.pop("_partial_json", "")
                    try:
                        block["input"] = json.loads(partial) if partial.strip() else {}
                    except json.JSONDecodeError:
                        block["input"] = {}
            elif kind == "message_delta":
                delta = event.get("delta") or {}
                if delta.get("stop_reason"):
                    stop_reason = delta["stop_reason"]
                usage.update(event.get("usage") or {})
            elif kind == "error":
                raise ModelError("stream error: " + json.dumps(event)[:400])
            elif kind == "message_stop":
                break
        return {
            "content": [blocks[index] for index in sorted(blocks)],
            "stop_reason": stop_reason,
            "usage": usage,
        }


# --------------------------------------------------------------------------- #
# task profile resolution
# --------------------------------------------------------------------------- #
def _load_toml(path: Path) -> dict:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
        import tomli as tomllib  # type: ignore
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _to_container(rel: str) -> str:
    return "C:\\task\\" + rel.replace("\\", "/").strip("/").replace("/", "\\")


def _guess_language(task_dir: Path, module_rel: Path) -> str:
    root = task_dir / module_rel
    if root.is_dir():
        suffixes = {p.suffix.lower() for p in root.rglob("*") if p.is_file()}
        if ".py" in suffixes and ".ps1" not in suffixes:
            return "python"
        if ".ps1" in suffixes:
            return "powershell"
    return "powershell"


def _autodetect_module(task_dir: Path) -> Path:
    """Fallback for a task.toml that carries no [policy].mutable_paths."""
    workspace = task_dir / "environment" / "workspace"
    skipped = {"docs", "assets", "tests", "__pycache__", ".pytest_cache"}
    if workspace.is_dir():
        for entry in sorted(workspace.iterdir()):
            if entry.is_dir() and entry.name.lower() not in skipped:
                return Path("environment") / "workspace" / entry.name
    return DEFAULT_PROFILE["module_rel"]


def resolve_task_profile(task_dir: Path) -> dict:
    """Derive the run profile from the task's own manifest.

    Everything the agent-facing prompt and write whitelist need is read from
    task.toml, so a new task needs no harness edits.
    """
    profile = dict(DEFAULT_PROFILE)
    data: dict = {}
    manifest = task_dir / "task.toml"
    if manifest.exists():
        try:
            data = _load_toml(manifest)
        except Exception as exc:  # noqa: BLE001 - the manifest is advisory
            log(f"  !! task.toml unreadable ({type(exc).__name__}: {exc}); using defaults")

    metadata = data.get("metadata") or {}
    policy = data.get("policy") or {}
    task_section = data.get("task") or {}
    profile["task_id"] = (metadata.get("task_id") or task_section.get("id")
                          or task_dir.name)

    mutable = [str(p) for p in (policy.get("mutable_paths") or [])]
    module_rel = (Path(mutable[0].replace("\\", "/").strip("/")) if mutable
                  else _autodetect_module(task_dir))
    profile["module_rel"] = module_rel
    profile["container_writable"] = _to_container(module_rel.as_posix())

    # Every markdown file under a read-only docs/ directory is reference
    # material. Some tasks deliberately ship a superseded draft there; the
    # instruction.md decides which source actually governs.
    docs: list[str] = []
    for entry in [str(p) for p in (policy.get("read_only_paths") or [])]:
        norm = entry.replace("\\", "/").rstrip("/")
        if not norm.endswith("/docs"):
            continue
        host_dir = task_dir / norm
        if host_dir.is_dir():
            for doc in sorted(host_dir.rglob("*.md")):
                docs.append(_to_container(doc.relative_to(task_dir).as_posix()))
    if not docs:
        host_dir = task_dir / "environment" / "workspace" / "docs"
        if host_dir.is_dir():
            for doc in sorted(host_dir.rglob("*.md")):
                docs.append(_to_container(doc.relative_to(task_dir).as_posix()))
    profile["contract_docs"] = docs

    samples = task_dir / "environment" / "workspace" / "assets"
    if samples.is_dir() and any(p.is_file() for p in samples.rglob("*")):
        profile["samples_dir"] = _to_container("environment/workspace/assets")
    else:
        profile["samples_dir"] = None

    tags = [str(t).lower() for t in (metadata.get("tags") or [])]
    if any("powershell" in t for t in tags):
        profile["language"] = "powershell"
    elif any("python" in t for t in tags):
        profile["language"] = "python"
    else:
        profile["language"] = _guess_language(task_dir, module_rel)
    return profile


# --------------------------------------------------------------------------- #
# agent tools
# --------------------------------------------------------------------------- #
def build_tools() -> list[dict]:
    writable = TASK_PROFILE["container_writable"]
    return [
        {
            "name": "list_dir",
            "description": "List the entries of a directory inside the container task tree.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": f"Container path, e.g. {writable}"}},
                "required": ["path"],
            },
        },
        {
            "name": "read_file",
            "description": ("Read a file from the container task tree. Text files come back with "
                            "line numbers; binary files come back as a hex dump."),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "description": "1-based first line (optional)"},
                    "end_line": {"type": "integer", "description": "1-based last line, inclusive (optional)"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": f"Create or overwrite a file. Only paths under {writable} are writable.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "finish",
            "description": ("Declare the work complete. Call this only when you believe the "
                            "implementation satisfies the specification."),
            "input_schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    ]

def build_system_prompt() -> str:
    profile = TASK_PROFILE
    lang = LANGUAGE_PROFILES.get(profile["language"], LANGUAGE_PROFILES["powershell"])
    writable = profile["container_writable"]

    reference_lines = []
    for doc in profile.get("contract_docs") or []:
        reference_lines.append(f"    - {doc}")
    if profile.get("samples_dir"):
        reference_lines.append(
            f"    - {profile['samples_dir']} (binary samples; read them with read_file, "
            "which returns a hex dump)")
    references = ""
    if reference_lines:
        references = ("\nReference material that ships with the task:\n"
                      + "\n".join(reference_lines) + "\n")

    return f"""You are {lang['persona']}. You work inside a
Windows Server Core container whose task tree is mounted at C:\\task, and you have a
separate set of tools to read and write files in that tree.

Your job: make the {lang['artifact_kind']} at
  {writable}
satisfy the task specification.

The authoritative task statement is:
  C:\\task\\instruction.md
{references}
Hard rules:
- You may only WRITE under {writable}.
- Everything else in the task tree is read-only. Do not modify it.
- {lang['target_note']}
- Keep the public API names, signatures and exported names exactly as the
  specification states.
- Where the task statement declares a document to be a draft or otherwise
  superseded, trust the sources it names instead of that document.

Working notes:
- The graders build their own fixtures; no grading fixture or scoring script is
  provided. Implement the specified behaviour rather than reverse-engineering one
  example.
- Your container is a read/write filesystem view only: you cannot execute code or
  run tests. Make the edit correct by reasoning about the specification and any
  authoritative samples.
- Binary files are readable through read_file, which returns a hex dump.
- Re-read the specification before you write. Most defects are small off-by-one,
  casing, ordering or framing mistakes.

When you are confident the specification is fully satisfied, call finish with a short summary.
"""


def build_task_prompt() -> str:
    docs = TASK_PROFILE.get("contract_docs") or []
    writable = TASK_PROFILE["container_writable"]
    parts = ["Read C:\\task\\instruction.md"]
    if docs:
        parts.append("and then " + ", ".join(docs))
    if TASK_PROFILE.get("samples_dir"):
        parts.append(f"and the samples under {TASK_PROFILE['samples_dir']}")
    parts.append(f"inspect {writable}")
    return (", ".join(parts)
            + ", and fix the implementation so it satisfies the specification. Start now.")


def translate_path(raw: str, mount: Path) -> Path:
    text = (raw or "").strip().strip('"').strip("'").replace("/", "\\")
    if text.upper().startswith("C:\\TASK"):
        rel = text[len("C:\\task"):].lstrip("\\")
    elif re.match(r"^[A-Za-z]:\\", text) or text.startswith("\\\\"):
        raise ValueError("path is outside the task tree; use paths under C:\\task")
    else:
        rel = text.lstrip("\\")
    host = (mount / rel).resolve()
    root = mount.resolve()
    if root not in host.parents and host != root:
        raise ValueError("path escapes the task tree")
    return host


def writable_root(mount: Path) -> Path:
    return (mount / TASK_PROFILE["module_rel"]).resolve()


def is_writable(host_path: Path, mount: Path) -> bool:
    try:
        host_path.resolve().relative_to(writable_root(mount))
        return True
    except ValueError:
        return False


def tool_list_dir(args: dict, container: str, mount: Path) -> str:
    host = translate_path(args["path"], mount)
    if not host.exists():
        return f"ERROR: no such directory: {args['path']}"
    lines = []
    for entry in sorted(host.iterdir(), key=lambda p: p.name.lower()):
        kind = "dir " if entry.is_dir() else "file"
        size = "" if entry.is_dir() else f" {entry.stat().st_size}b"
        lines.append(f"{kind}{size}\t{entry.name}")
    return "\n".join(lines) or "(empty)"


def _looks_binary(raw: bytes) -> bool:
    if b"\x00" in raw:
        return True
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def tool_read_file(args: dict, container: str, mount: Path) -> str:
    host = translate_path(args["path"], mount)
    if not host.is_file():
        return f"ERROR: no such file: {args['path']}"
    raw = host.read_bytes()

    # Binary fixtures are part of the task surface on several tasks (e.g. the
    # authoritative .wfmt samples on wfflab__wfmt-215). Handing the model a
    # hex dump is the only way it can reason about their exact bytes, since the
    # container deliberately exposes no execution.
    if _looks_binary(raw):
        truncated = len(raw) > MAX_BINARY_DUMP_BYTES
        body_bytes = raw[:MAX_BINARY_DUMP_BYTES]
        rows = []
        for offset in range(0, len(body_bytes), 16):
            chunk = body_bytes[offset:offset + 16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            if len(chunk) > 8:
                hex_part = hex_part[:23] + "  " + hex_part[23:]
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            rows.append(f"{offset:08x}  {hex_part:<48}  |{ascii_part}|")
        total = len(rows)
        start = max(1, int(args.get("start_line") or 1))
        end = min(total, int(args.get("end_line") or total))
        header = (f"(binary file, {len(raw)} bytes -- hex dump, 16 bytes per line"
                  + (f", truncated to the first {MAX_BINARY_DUMP_BYTES} bytes" if truncated else "")
                  + ")\n")
        return header + f"({total} lines total)\n" + "\n".join(rows[start - 1:end])

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "ERROR: file is neither valid UTF-8 text nor detected as binary"
    lines = text.splitlines()
    start = max(1, int(args.get("start_line") or 1))
    end = min(len(lines), int(args.get("end_line") or len(lines)))
    body = "\n".join(f"{i:4d}| {lines[i - 1]}" for i in range(start, end + 1))
    return f"({len(lines)} lines total)\n{body}"


def tool_write_file(args: dict, container: str, mount: Path) -> str:
    host = translate_path(args["path"], mount)
    if not is_writable(host, mount):
        return (f"ERROR: only paths under {TASK_PROFILE['container_writable']} "
                "are writable")
    host.parent.mkdir(parents=True, exist_ok=True)
    content = args.get("content", "")
    host.write_text(content, encoding="utf-8", newline="\r\n")
    return f"wrote {len(content)} chars to {args['path']}"


def tool_run_shell(args: dict, container: str, mount: Path) -> str:
    command = args.get("command", "")
    timeout = int(args.get("timeout_sec") or 600)
    timeout = max(10, min(timeout, 3600))
    proc = ps_exec(container, command, timeout=timeout + 30)
    output = (proc.stdout or "") + (proc.stderr or "")
    return output.strip()[-12000:] or f"(no output, exit code {proc.returncode})"


def run_agent(cfg: dict, view_dir: Path, container: str, agent_log: Path) -> dict:
    mount = view_dir
    client = ModelClient(cfg, agent_log)
    before = workspace_fingerprint(view_dir)

    messages: list[dict] = [{
        "role": "user",
        "content": build_task_prompt(),
    }]

    turns = 0
    tool_calls = 0
    status = "completed"
    summary = ""
    truncations = 0

    while turns < MAX_AGENT_TURNS:
        turns += 1
        try:
            response = client.call(build_system_prompt(), messages, build_tools())
        except ModelError as exc:
            return {"status": "error", "turns": turns, "tool_calls": tool_calls,
                    "summary": f"model error: {exc}"}

        blocks = [b for b in response.get("content", []) if b.get("type") != "thinking"]
        assistant_text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if assistant_text.strip():
            client._log(f"--- turn {turns} assistant ---\n{assistant_text.strip()}")

        stop_reason = response.get("stop_reason")
        messages.append({"role": "assistant", "content": blocks})

        tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
        if not tool_uses:
            if stop_reason == "max_tokens" and truncations < 2:
                truncations += 1
                messages.append({"role": "user", "content": "Your reply was cut off. Continue, and use tools."})
                continue
            if tool_calls > 0:
                # The agent did real work in earlier turns and ended with a
                # prose wrap-up instead of the finish tool.  This is a scored
                # completion, not a harness fault -- only a run that NEVER
                # emitted a tool call is "no_tool_call".
                status = "completed"
            else:
                status = "no_tool_call"
            summary = assistant_text.strip()[:500]
            break

        results = []
        finished = False
        for call in tool_uses:
            tool_calls += 1
            name = call.get("name")
            args = call.get("input") or {}
            client._log(f"--- turn {turns} tool {name} {json.dumps(args)[:400]}")
            try:
                if name == "list_dir":
                    output = tool_list_dir(args, container, mount)
                elif name == "read_file":
                    output = tool_read_file(args, container, mount)
                elif name == "write_file":
                    output = tool_write_file(args, container, mount)
                elif name == "run_shell":
                    output = tool_run_shell(args, container, mount)
                elif name == "finish":
                    summary = str(args.get("summary", ""))[:1000]
                    output = "acknowledged"
                    finished = True
                else:
                    output = f"ERROR: unknown tool {name}"
                is_error = output.startswith("ERROR")
            except Exception as exc:  # noqa: BLE001 - tool layer
                output = f"ERROR: {type(exc).__name__}: {exc}"
                is_error = True
            client._log(f"--- turn {turns} result ---\n{output[:2000]}")
            results.append({
                "type": "tool_result",
                "tool_use_id": call.get("id"),
                "content": output,
                "is_error": is_error,
            })
        if finished:
            status = "completed"
            break
        messages.append({"role": "user", "content": results})
    else:
        status = "max_turns"

    # keep the transcript compact for storage
    try:
        (agent_log).open("a", encoding="utf-8").write(
            f"\n=== agent finished status={status} turns={turns} tool_calls={tool_calls} ===\n"
        )
    except OSError:
        pass

    after = workspace_fingerprint(view_dir)
    return {
        "status": status,
        "turns": turns,
        "tool_calls": tool_calls,
        "summary": summary,
        "changed_workspace": before != after,
    }


# --------------------------------------------------------------------------- #
# run orchestration
# --------------------------------------------------------------------------- #
def collect_run_artifacts(case_dir: Path, run_dir: Path, log_text: str) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "test.log").write_text(log_text, encoding="utf-8")

    result_source = case_dir / "results" / "result.json"
    checks_source = case_dir / "results" / "checks.json"
    if not result_source.exists():
        result = {
            "task_id": None, "task_version": None, "mode": None,
            "verdict": "INVALID", "reason": "verifier produced no result.json",
            "test": {"report": {"status": "INVALID", "score": None}},
        }
    else:
        raw = result_source.read_text(encoding="utf-8-sig")
        result = json.loads(raw)
        if checks_source.exists():
            shutil.copy2(checks_source, run_dir / "checks.json")
    return result


def write_result(run_dir: Path, result: dict) -> None:
    (run_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run_once(task_dir: Path, image: str, mode: str, cfg: dict | None,
             label: str, run_id: str, keep: bool) -> dict:
    run_dir = WORKSPACE_ROOT / "runs" / task_dir.name / run_id / label
    work_dir = WORKSPACE_ROOT / "work" / run_id
    case_dir = work_dir / "case"
    view_dir = work_dir / "view"
    container = f"oh-{re.sub(r'[^a-z0-9]+', '-', run_id.lower())}"

    log(f"run {run_id} [{mode}] -> {run_dir.relative_to(WORKSPACE_ROOT)}")
    started = time.time()
    # Create the run directory before anything can write into it; the candidate
    # transcript and the stderr capture both stream into it while the run is
    # still in flight.
    run_dir.mkdir(parents=True, exist_ok=True)
    capture_run_identity(run_dir)
    copy_tree(task_dir, case_dir)

    agent_info: dict = {}
    try:
        if mode == "golden":
            start_container(image, case_dir, container)
            proc = ps_exec(container,
                           f"& '{CONTAINER_TASK_ROOT}\\solution\\solve.ps1' -TaskRoot '{CONTAINER_TASK_ROOT}'",
                           timeout=900)
            if proc.returncode != 0:
                raise DockerError(f"solve.ps1 failed: {(proc.stdout or proc.stderr)[-800:]}")

        elif mode == "candidate":
            assert cfg is not None
            build_agent_view(case_dir, view_dir)
            start_container(image, view_dir, container)
            agent_info = run_agent(cfg, view_dir, container, run_dir / "agent.log")
            stop_container(container)
            mirror_workspace(view_dir, case_dir)

        elif mode == "no-change":
            pass

        else:
            raise DockerError(f"unsupported mode {mode}")

        # ---- verification ---------------------------------------------------
        start_container(image, case_dir, container)
        proc = ps_exec(container,
                       f"& '{CONTAINER_TASK_ROOT}\\environment\\run.ps1' -TaskRoot '{CONTAINER_TASK_ROOT}'",
                       timeout=7200)
        # PowerShell serialises anything written to its error stream as CLIXML,
        # which would drown the human-readable check lines. Keep the two streams
        # apart so test.log stays legible; fall back to stderr when nothing was
        # written to stdout at all.
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        (run_dir).mkdir(parents=True, exist_ok=True)
        (run_dir / "stderr.log").write_text(stderr_text, encoding="utf-8")
        log_text = stdout_text
        if "checks:" not in stdout_text and stderr_text:
            log_text = stdout_text + "\n--- stderr ---\n" + stderr_text
        log(f"  verifier exit={proc.returncode}")
    except Exception as exc:  # noqa: BLE001 - orchestration layer
        log(f"  RUN FAILED: {exc}")
        log_text = f"runner failure: {type(exc).__name__}: {exc}\n"
        proc = None
    finally:
        stop_container(container)

    result = collect_run_artifacts(case_dir, run_dir, log_text)
    result["mode"] = mode
    if TASK_IDENTITY:
        result["task_identity"] = dict(TASK_IDENTITY)
    if cfg:
        # `model_alias` must be the short qualification alias (QWEN/OPUS/GLM/KIMI):
        # summarize_model_runs.py matches it with str(...).upper() == model.
        result["model_alias"] = cfg.get("alias") or cfg.get("label")
        result["model_key"] = cfg.get("key")
    if agent_info:
        result["agent"] = agent_info
    result["duration_seconds"] = round(time.time() - started, 1)
    result["runner"] = {"run_id": run_id, "label": label, "finished_at": now_iso()}
    write_result(run_dir, result)

    report = (result.get("test") or {}).get("report") or {}
    log(f"  -> verdict={result.get('verdict')} status={report.get('status')}")
    if not keep:
        shutil.rmtree(work_dir, ignore_errors=True)
    return result


def build_model_config(env: dict, alias: str) -> dict:
    prefix = f"{alias}_"
    def need(key: str) -> str:
        value = env.get(prefix + key)
        if not value:
            raise SystemExit(f"missing {prefix}{key} in .env.local")
        return value

    cfg = {
        "alias": alias,
        "label": env.get(prefix + "LABEL") or alias,
        "dir": env.get(prefix + "DIR") or alias.lower(),
        "base_url": need("BASE_URL"),
        "api_key": need("API_KEY"),
        "model": need("MODEL"),
        "auth": env.get(prefix + "AUTH", "x-api-key"),
        "max_tokens": int(env.get(prefix + "MAX_TOKENS", "16000")),
        "request_timeout": int(env.get(prefix + "REQUEST_TIMEOUT", "900")),
        # Some gateways cut a *non-streaming* response at a fixed wall-clock
        # limit (126 s measured on api.ebondai.com) although the upstream keeps
        # generating; the retry then re-sends a byte-identical payload and hits
        # the same wall. Asking for stream=true keeps bytes flowing, so the cap
        # does not apply and max_tokens can be sized for the task instead of
        # for the transport. Opt-in per model via <ALIAS>_STREAM=1.
        "stream": str(env.get(prefix + "STREAM", "")).strip().lower()
        in {"1", "true", "yes", "on"},
    }
    extra = env.get(prefix + "EXTRA_JSON")
    if extra:
        cfg["extra_body"] = json.loads(extra)
    return cfg


def main() -> int:
    global WORKSPACE_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="task id under tasks/ or a task directory")
    parser.add_argument("--mode", required=True,
                        choices=["no-change", "golden", "candidate", "matrix", "run"])
    parser.add_argument("--models", default="", help="comma separated aliases, e.g. QWEN,OPUS")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT))
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--env-file", default=str(WORKSPACE_ROOT / ".env.local"))
    args = parser.parse_args()

    WORKSPACE_ROOT = Path(args.workspace_root).resolve()

    candidate = Path(args.task)
    if not candidate.exists():
        candidate = WORKSPACE_ROOT / "tasks" / args.task
    if not candidate.exists():
        raise SystemExit(f"task not found: {args.task}")
    task_dir = candidate.resolve()

    TASK_PROFILE.update(resolve_task_profile(task_dir))
    log(f"task profile: module={TASK_PROFILE['module_rel'].as_posix()} "
        f"language={TASK_PROFILE['language']} "
        f"docs={len(TASK_PROFILE.get('contract_docs') or [])} "
        f"samples={'yes' if TASK_PROFILE.get('samples_dir') else 'no'}")

    ok, detail = docker_ok()
    if not ok:
        raise SystemExit(f"docker server not reachable: {detail}")
    if not detail.lower().startswith("windows"):
        raise SystemExit(
            f"docker is serving {detail}; switch Docker Desktop to Windows containers "
            "(docker desktop engine use windows) before running this task"
        )

    image = ensure_image(task_dir)
    log(f"image ready: {image}")

    global TASK_IDENTITY
    TASK_IDENTITY = build_task_identity(task_dir, image)
    log(f"task identity: {TASK_IDENTITY['task_id']}@{TASK_IDENTITY['task_version']} "
        f"task_hash={TASK_IDENTITY['task_hash']} "
        f"image_digest={TASK_IDENTITY['docker_image_digest'][:19]}")

    env = load_env_file(Path(args.env_file))

    jobs: list[tuple[str, dict | None, str]] = []
    if args.mode == "no-change":
        for _ in range(args.runs):
            jobs.append(("no-change", None, "no-change"))
    elif args.mode == "golden":
        for _ in range(args.runs):
            jobs.append(("golden", None, "golden"))
    else:
        aliases = [a.strip().upper() for a in args.models.split(",") if a.strip()]
        if not aliases:
            raise SystemExit("--models is required for candidate/matrix/run modes")
        for alias in aliases:
            cfg = build_model_config(env, alias)
            for _ in range(args.runs):
                jobs.append(("candidate", cfg, cfg["dir"]))

    results = []
    for index, (mode, cfg, label) in enumerate(jobs, start=1):
        stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        # Parallel shards can start inside the same second, and two shards of
        # the same model produce an identical stamp+label pair. Without a
        # unique token they would share both a work directory and a container
        # name and corrupt each other (observed 2026-10-07: three QWEN shards
        # collided and all three died inside copy_tree). A per-process random
        # suffix keeps run_id unique; nothing downstream parses its shape.
        run_id = f"{stamp}-{mode}-{label}-{index:02d}-{secrets.token_hex(2)}"
        results.append(run_once(task_dir, image, mode, cfg, label, run_id, args.keep_work))

    print()
    for result in results:
        report = (result.get("test") or {}).get("report") or {}
        print(f"  {result['runner']['run_id']:<52} verdict={result.get('verdict')} "
              f"status={report.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
