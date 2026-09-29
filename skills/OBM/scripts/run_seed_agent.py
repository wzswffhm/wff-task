#!/usr/bin/env python3
"""Run Doubao Seed Evolving as a tool-using coding agent in one repository."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - exercised by installation checks
    raise SystemExit(
        "缺少 openai Python SDK。请先运行：python3 -m pip install 'openai>=1.68,<3'"
    ) from exc


DEFAULT_MODEL = "doubao-seed-evolving"
MAX_FILE_BYTES = 1_000_000
MAX_TOOL_OUTPUT = 30_000
BLOCKED_COMMAND_PATTERNS = (
    r"\bcurl\b",
    r"\bwget\b",
    r"\bnc\b",
    r"\bncat\b",
    r"\bssh\b",
    r"\bscp\b",
    r"\brsync\b",
    r"\bgit\s+(?:clone|fetch|pull|push)\b",
    r"\bpip(?:3)?\s+install\b",
    r"\bpython(?:3)?\s+-m\s+pip\s+install\b",
    r"\bapt(?:-get)?\b",
    r"\bbrew\b",
    r"\bnpm\s+(?:install|add)\b",
    r"\byarn\s+add\b",
    r"\bpnpm\s+(?:install|add)\b",
)
PATCH_EXCLUDES = (
    ":(exclude)**/__pycache__/**",
    ":(exclude)**/.pytest_cache/**",
    ":(exclude)**/.mypy_cache/**",
    ":(exclude)**/.ruff_cache/**",
    ":(exclude)**/*.pyc",
    ":(exclude)**/*.pyo",
    ":(exclude)**/.coverage",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{path}:{number} 不是有效的 KEY=value 格式")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def pick(values: dict[str, str], *names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name) or values.get(name)
        if value:
            return value
    return None


def truncate(text: str | bytes | None, limit: int = MAX_TOOL_OUTPUT) -> str:
    if text is None:
        text = ""
    elif isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    if len(text) <= limit:
        return text
    removed = len(text) - limit
    return text[:limit] + f"\n...[截断 {removed} 个字符]"


class Workspace:
    def __init__(
        self,
        root: Path,
        command_timeout: int,
        docker: str,
        command_image: str,
    ) -> None:
        self.root = root.resolve()
        self.command_timeout = command_timeout
        self.docker = docker
        self.command_image = command_image

    def resolve(self, relative: str) -> Path:
        value = relative.strip() or "."
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"路径越出工作区：{relative}") from exc
        return candidate

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def list_files(self, path: str = ".", max_depth: int = 3) -> dict[str, Any]:
        base = self.resolve(path)
        if not base.exists():
            raise FileNotFoundError(path)
        if base.is_file():
            return {"files": [self.relative(base)]}
        max_depth = max(0, min(int(max_depth), 8))
        prefix_depth = len(base.relative_to(self.root).parts)
        rows: list[str] = []
        for item in sorted(base.rglob("*")):
            rel = item.relative_to(self.root)
            if ".git" in rel.parts:
                continue
            depth = len(rel.parts) - prefix_depth
            if depth > max_depth:
                continue
            label = rel.as_posix() + ("/" if item.is_dir() else "")
            rows.append(label)
            if len(rows) >= 2000:
                break
        return {"files": rows, "truncated": len(rows) >= 2000}

    def read_file(
        self, path: str, start_line: int = 1, end_line: int = 400
    ) -> dict[str, Any]:
        target = self.resolve(path)
        if not target.is_file():
            raise FileNotFoundError(path)
        if target.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"文件过大，无法读取：{path}")
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = max(1, int(start_line))
        end = min(len(lines), max(start, int(end_line)))
        numbered = "\n".join(
            f"{index:6d}\t{lines[index - 1]}" for index in range(start, end + 1)
        )
        return {
            "path": self.relative(target),
            "start_line": start,
            "end_line": end,
            "total_lines": len(lines),
            "content": truncate(numbered),
        }

    def search_text(
        self, query: str, path: str = ".", glob: str = "*", max_results: int = 100
    ) -> dict[str, Any]:
        base = self.resolve(path)
        pattern = re.compile(query)
        results: list[dict[str, Any]] = []
        files = [base] if base.is_file() else base.rglob("*")
        for candidate in files:
            if not candidate.is_file():
                continue
            rel = candidate.relative_to(self.root)
            if ".git" in rel.parts or not fnmatch.fnmatch(candidate.name, glob):
                continue
            try:
                resolved = candidate.resolve()
                resolved.relative_to(self.root)
            except (OSError, ValueError):
                continue
            if candidate.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                lines = resolved.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(lines, 1):
                if pattern.search(line):
                    results.append(
                        {"path": rel.as_posix(), "line": number, "text": line[:1000]}
                    )
                    if len(results) >= max(1, min(int(max_results), 500)):
                        return {"matches": results, "truncated": True}
        return {"matches": results, "truncated": False}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        target = self.resolve(path)
        if ".git" in target.relative_to(self.root).parts:
            raise ValueError("不能修改 .git")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise ValueError("单次写入超过 1 MB")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
        return {"path": self.relative(target), "bytes": len(encoded)}

    def apply_patch(self, patch: str) -> dict[str, Any]:
        if len(patch.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError("patch 超过 1 MB")
        for line in patch.splitlines():
            if line.startswith(("+++ ", "--- ")):
                name = line[4:].split("\t", 1)[0]
                if name == "/dev/null":
                    continue
                if name.startswith(("a/", "b/")):
                    name = name[2:]
                self.resolve(name)
                if ".git" in Path(name).parts:
                    raise ValueError("不能修改 .git")
        result = subprocess.run(
            ["git", "apply", "--recount", "--whitespace=nowarn", "-"],
            cwd=self.root,
            input=patch,
            text=True,
            capture_output=True,
        )
        return {
            "exit_code": result.returncode,
            "stdout": truncate(result.stdout),
            "stderr": truncate(result.stderr),
        }

    def run_command(self, command: str, timeout: Optional[int] = None) -> dict[str, Any]:
        if not command.strip():
            raise ValueError("命令不能为空")
        if len(command) > 4000:
            raise ValueError("命令过长")
        for pattern in BLOCKED_COMMAND_PATTERNS:
            if re.search(pattern, command, flags=re.IGNORECASE):
                raise ValueError("禁止联网、安装依赖或修改远端：" + command)
        actual_timeout = max(1, min(int(timeout or self.command_timeout), 600))
        try:
            result = subprocess.run(
                [
                    self.docker,
                    "run",
                    "--rm",
                    "--network=none",
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "-e",
                    "HOME=/tmp",
                    "-e",
                    "PYTHONDONTWRITEBYTECODE=1",
                    "-e",
                    "PYTEST_ADDOPTS=-p no:cacheprovider",
                    "-v",
                    f"{self.root}:/app",
                    "-w",
                    "/app",
                    self.command_image,
                    "/bin/bash",
                    "-lc",
                    command,
                ],
                text=True,
                capture_output=True,
                timeout=actual_timeout,
            )
            return {
                "exit_code": result.returncode,
                "stdout": truncate(result.stdout),
                "stderr": truncate(result.stderr),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "exit_code": 124,
                "stdout": truncate(exc.stdout or ""),
                "stderr": truncate((exc.stderr or "") + "\n命令超时"),
            }

    def git_diff(self) -> dict[str, Any]:
        result = subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
        )
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.root,

            text=True,
            capture_output=True,
            check=True,
        )
        return {"status": status.stdout, "diff": truncate(result.stdout)}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出工作区内的文件和目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "max_depth": {"type": "integer", "default": 3},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "按行读取工作区内的文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "default": 1},
                    "end_line": {"type": "integer", "default": 400},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "使用正则表达式搜索工作区文本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "glob": {"type": "string", "default": "*"},
                    "max_results": {"type": "integer", "default": 100},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "在工作区内创建或完整覆盖一个文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "在工作区 Git 仓库中应用 unified diff。",
            "parameters": {
                "type": "object",
                "properties": {"patch": {"type": "string"}},
                "required": ["patch"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在工作区根目录执行本地命令。禁止联网和安装依赖。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": 120},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "查看当前工作区相对基线的 Git 状态和 diff。",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]


def call_tool(workspace: Workspace, name: str, arguments: dict[str, Any]) -> Any:
    methods = {
        "list_files": workspace.list_files,
        "read_file": workspace.read_file,
        "search_text": workspace.search_text,
        "write_file": workspace.write_file,
        "apply_patch": workspace.apply_patch,
        "run_command": workspace.run_command,
        "git_diff": workspace.git_diff,
    }
    if name not in methods:
        raise ValueError(f"未知工具：{name}")
    return methods[name](**arguments)


def write_patch(repo: Path, output: Path) -> None:
    subprocess.run(["git", "add", "-N", "--", "."], cwd=repo, check=True)
    try:
        result = subprocess.run(
            ["git", "diff", "--binary", "HEAD", "--", ".", *PATCH_EXCLUDES],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        )
        # newline="" keeps the patch bytes exactly as git emitted them; the
        # default Windows text-mode translation would turn every LF into
        # CRLF and make `git apply` fail inside the (Linux) verifier.
        output.write_text(result.stdout, encoding="utf-8", newline="")
    finally:
        subprocess.run(
            ["git", "reset", "--mixed", "-q", "HEAD"], cwd=repo, check=True
        )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def write_progress(
    output_dir: Path,
    status: str,
    turns: int,
    tool_calls: int,
    usage: dict[str, int],
    started: float,
    last_event: str,
    last_tool: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    write_json_atomic(
        output_dir / "PROGRESS.json",
        {
            "status": status,
            "turns": turns,
            "tool_calls": tool_calls,
            "usage": usage,
            "duration_seconds": round(time.time() - started, 3),
            "last_event": last_event,
            "last_tool": last_tool,
            "error": error,
            "updated_at": utc_now(),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path("model.env"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default="minimal")
    parser.add_argument("--max-turns", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--command-timeout", type=int, default=120)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--command-image", required=True)
    args = parser.parse_args()

    repo = args.repo.expanduser().resolve()
    prompt_path = args.prompt.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    env_path = args.env_file.expanduser().resolve()
    if not (repo / ".git").is_dir():
        raise SystemExit(f"不是 Git 工作区：{repo}")
    if subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout:
        raise SystemExit(f"Seed 运行前工作区必须干净：{repo}")
    if not prompt_path.is_file():
        raise SystemExit(f"找不到提示词：{prompt_path}")
    if not env_path.is_file():
        raise SystemExit(f"找不到模型配置：{env_path}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"输出目录非空，拒绝覆盖：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        values = load_env(env_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    api_key = pick(values, "OPENAI_API_KEY", "openai_api_key", "API_KEY", "api_key", "key")
    base_url = pick(values, "OPENAI_BASE_URL", "openai_base_url", "BASE_URL", "base_url", "url")
    if not api_key or not base_url:
        raise SystemExit(f"{env_path} 必须包含 key=... 和 url=...")

    image_check = subprocess.run(
        [args.docker, "image", "inspect", args.command_image],
        text=True,
        capture_output=True,
    )
    if image_check.returncode != 0:
        raise SystemExit(f"找不到命令执行镜像：{args.command_image}")

    prompt = prompt_path.read_text(encoding="utf-8")
    workspace = Workspace(repo, args.command_timeout, args.docker, args.command_image)
    client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
    transcript = output_dir / "TRANSCRIPT.jsonl"
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是软件工程 Agent。你必须使用工具检查并修改当前工作区，实际运行合适的测试。"
                "只能处理当前仓库；禁止联网、安装依赖、读取仓库外文件或修改测试来规避任务。"
                "完成后给出简短总结和实际测试结果。"
            ),
        },
        {"role": "user", "content": prompt},
    ]
    started = time.time()
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    final_text = ""
    status = "max_turns"
    error = None
    turns_completed = 0
    tool_calls_total = 0
    write_progress(
        output_dir,
        status="running",
        turns=0,
        tool_calls=0,
        usage=usage,
        started=started,
        last_event="agent_started",
    )

    try:
        for turn in range(1, args.max_turns + 1):
            response = client.chat.completions.create(
                model=args.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                reasoning_effort=args.reasoning_effort,
                max_tokens=args.max_tokens,
            )
            turns_completed = turn
            if response.usage:
                for key in usage:
                    usage[key] += int(getattr(response.usage, key, 0) or 0)
            choice = response.choices[0]
            message = choice.message
            assistant_payload = message.model_dump(exclude_none=True)
            messages.append(assistant_payload)
            append_jsonl(
                transcript,
                {
                    "event": "assistant",
                    "turn": turn,
                    "finish_reason": choice.finish_reason,
                    "content": message.content,
                    "tool_calls": [
                        item.model_dump(exclude_none=True) for item in (message.tool_calls or [])
                    ],
                },
            )
            write_progress(
                output_dir,
                status="running",
                turns=turns_completed,
                tool_calls=tool_calls_total,
                usage=usage,
                started=started,
                last_event="assistant_response",
            )
            if not message.tool_calls:
                final_text = message.content or ""
                status = "completed" if tool_calls_total else "invalid_agent_completion"
                if not tool_calls_total:
                    error = "Seed 未调用任何工作区工具，不能作为有效 Agent 实验"
                break

            for tool_call in message.tool_calls:
                tool_calls_total += 1
                arguments: dict[str, Any] = {}
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                    result = call_tool(workspace, tool_call.function.name, arguments)
                    tool_result = {"ok": True, "result": result}
                except Exception as exc:  # tool failures are returned to the model
                    tool_result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                content = json.dumps(tool_result, ensure_ascii=False)
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": content}
                )
                append_jsonl(
                    transcript,
                    {
                        "event": "tool",
                        "turn": turn,
                        "name": tool_call.function.name,
                        "arguments": arguments,
                        "output": tool_result,
                    },
                )
                write_progress(
                    output_dir,
                    status="running",
                    turns=turns_completed,
                    tool_calls=tool_calls_total,
                    usage=usage,
                    started=started,
                    last_event="tool_result",
                    last_tool=tool_call.function.name,
                )
    except Exception as exc:
        status = "api_or_runtime_error"
        error = f"{type(exc).__name__}: {exc}"
        write_progress(
            output_dir,
            status=status,
            turns=turns_completed,
            tool_calls=tool_calls_total,
            usage=usage,
            started=started,
            last_event="agent_error",
            error=error,
        )

    (output_dir / "FINAL_RESPONSE.md").write_text(final_text + "\n", encoding="utf-8")
    write_patch(repo, output_dir / "model.patch")
    run_record = {
        "status": status,
        "error": error,
        "model_requested": args.model,
        "reasoning_effort": args.reasoning_effort,
        "max_tokens": args.max_tokens,
        "endpoint_host": urlparse(base_url).netloc,
        "prompt_sha256": sha256(prompt_path),
        "baseline_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip(),
        "turns": turns_completed,
        "tool_calls": tool_calls_total,
        "max_turns": args.max_turns,
        "duration_seconds": round(time.time() - started, 3),
        "usage": usage,
        "patch_sha256": sha256(output_dir / "model.patch"),
        "patch_bytes": (output_dir / "model.patch").stat().st_size,
    }
    write_json_atomic(output_dir / "API_RUN.json", run_record)
    write_progress(
        output_dir,
        status=status,
        turns=turns_completed,
        tool_calls=tool_calls_total,
        usage=usage,
        started=started,
        last_event="agent_finished",
        error=error,
    )
    print(json.dumps(run_record, ensure_ascii=False, indent=2))
    return 0 if status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
