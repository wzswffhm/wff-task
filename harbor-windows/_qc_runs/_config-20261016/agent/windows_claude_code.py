"""Windows Harbor adapter for Claude Code compatible model endpoints.

The task instruction is uploaded as an exact UTF-8 file and piped to Claude Code
through stdin. Credentials remain in the host process environment and are passed
directly to the container exec call; they are never represented as explicit
Harbor agent environment values or command-line arguments.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import override

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class WindowsClaudeCodeAgent(BaseAgent):
    SUPPORTS_WINDOWS = True
    _RUNNER = r'''$ErrorActionPreference = 'Stop'
$workdir = if ($env:WINDOWS_CLAUDE_WORKDIR) { $env:WINDOWS_CLAUDE_WORKDIR } else { 'C:\testbed' }
Set-Location $workdir
$inputPath = 'C:\harbor-agent-input\instruction.txt'
$bytes = [IO.File]::ReadAllBytes($inputPath)
$sha256 = [Security.Cryptography.SHA256]::Create()
try {
    $sha = ([BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
} finally {
    $sha256.Dispose()
}
Write-Output ('INSTRUCTION_UTF8_BYTES=' + $bytes.Length)
Write-Output ('INSTRUCTION_SHA256=' + $sha)
$instruction = [IO.File]::ReadAllText($inputPath, [Text.UTF8Encoding]::new($false, $true))
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$relayPrefix = 'http://host.docker.internal:'
if ($env:ANTHROPIC_BASE_URL.TrimEnd('/').StartsWith($relayPrefix)) {
    $relayPort = ([Uri]$env:ANTHROPIC_BASE_URL.TrimEnd('/')).Port
    $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
        Where-Object { $_.NextHop -and $_.NextHop -ne '0.0.0.0' } |
        Sort-Object RouteMetric |
        Select-Object -First 1
    if (-not $route) { throw 'No container default gateway for Qwen relay' }
    $env:ANTHROPIC_BASE_URL = 'http://' + $route.NextHop + ':' + $relayPort
}
$probePath = 'C:\logs\agent\connection-probe.txt'
('PROXY_ENV_AFTER_CLEAR=' + ((Get-ChildItem Env:*PROXY* | ForEach-Object { $_.Name + '=' + $_.Value }) -join ';')) | Set-Content -LiteralPath $probePath
try {
    $endpoint = [Uri]$env:ANTHROPIC_BASE_URL
    $probe = & curl.exe -sS -o NUL -w '%{http_code}' --max-time 12 ($endpoint.GetLeftPart([System.UriPartial]::Authority) + $endpoint.AbsolutePath) 2>&1
    Add-Content -LiteralPath $probePath -Value ('MODEL_ENDPOINT_HTTP_STATUS=' + $probe)
} catch {
    Add-Content -LiteralPath $probePath -Value ('MODEL_ENDPOINT_PROBE_ERROR=' + $_.Exception.GetType().Name)
}
$instruction | & C:\node\claude.cmd --verbose --output-format stream-json --print --dangerously-skip-permissions --disallowedTools WebSearch,WebFetch 2>&1 | Tee-Object -FilePath C:\logs\agent\claude-code.jsonl
$rc = $LASTEXITCODE
$ErrorActionPreference = $previousPreference
Write-Output ('EXIT=' + $rc)
Remove-Item -LiteralPath $inputPath -Force -ErrorAction SilentlyContinue
exit $rc
'''

    @staticmethod
    @override
    def name() -> str:
        return "windows-claude-code"

    @override
    def version(self) -> str:
        return "1.0.0"

    @staticmethod
    def _workdir() -> str:
        return os.environ.get("WINDOWS_CLAUDE_WORKDIR", r"C:\testbed")

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        workdir = self._workdir()
        safe_workdir = workdir.replace("\\", "/")
        result = await environment.exec(
            command=(
                "powershell.exe -NoLogo -NoProfile -NonInteractive "
                "-ExecutionPolicy Bypass -Command \""
                "$ErrorActionPreference='Stop'; "
                f"Set-Location '{workdir}'; "
                f"git config --global --add safe.directory {safe_workdir}; "
                "if (-not (Test-Path C:\\node\\claude.cmd)) { throw 'claude.cmd missing' }; "
                "& C:\\node\\claude.cmd --version\""
            ),
            timeout_sec=120,
        )
        if result.return_code != 0:
            raise RuntimeError("Claude Code or the frozen Git checkout is unavailable")

    def _model_env(self) -> dict[str, str]:
        key = os.environ.get("WINDOWS_CLAUDE_API_KEY", "")
        base_url = os.environ.get("WINDOWS_CLAUDE_BASE_URL", "")
        model = os.environ.get("WINDOWS_CLAUDE_MODEL") or self.model_name or ""
        if not key or not base_url or not model:
            raise RuntimeError("Windows Claude Code model profile is incomplete")
        return {
            "ANTHROPIC_API_KEY": key,
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_MODEL": model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
            "CLAUDE_CODE_SUBAGENT_MODEL": model,
            "CLAUDE_CODE_NO_MODEL_FALLBACK": "true",
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1000000",
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
            "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80",
            "API_TIMEOUT_MS": "900000",
            "BASH_DEFAULT_TIMEOUT_MS": "600000",
            "CLAUDE_CODE_MAX_RETRIES": "8",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "128000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "IS_SANDBOX": "1",
            # The frozen image / Docker inject a host-local proxy (127.0.0.1:10090)
            # that is not reachable from inside Windows containers. Empty overlays
            # force a direct connection to the profile's explicit endpoint.
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "ALL_PROXY": "",
            "NO_PROXY": "*",
            "http_proxy": "",
            "https_proxy": "",
            "all_proxy": "",
            "no_proxy": "*",
        }

    @staticmethod
    def _populate_context_from_stream(output: str, context: AgentContext) -> None:
        """Populate Harbor metrics from Claude Code's terminal result event."""
        result_event: dict | None = None
        events = 0
        for line in output.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            events += 1
            if event.get("type") == "result":
                result_event = event

        if result_event is None:
            return
        usage = result_event.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        direct_input = int(usage.get("input_tokens") or 0)
        cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
        cache_read = int(usage.get("cache_read_input_tokens") or 0)
        context.n_input_tokens = direct_input + cache_creation + cache_read
        context.n_cache_tokens = cache_creation + cache_read
        context.n_output_tokens = int(usage.get("output_tokens") or 0)
        total_cost = result_event.get("total_cost_usd")
        context.cost_usd = float(total_cost) if isinstance(total_cost, (int, float)) else None
        context.metadata = {
            **(context.metadata or {}),
            "stream_events": events,
            "turns": int(result_event.get("num_turns") or 0),
            "duration_ms": int(result_event.get("duration_ms") or 0),
            "duration_api_ms": int(result_event.get("duration_api_ms") or 0),
            "result_subtype": result_event.get("subtype"),
        }

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        instruction_bytes = instruction.encode("utf-8")
        instruction_hash = hashlib.sha256(instruction_bytes).hexdigest()
        with tempfile.TemporaryDirectory(prefix="windows-claude-instruction-") as temp:
            source = Path(temp) / "instruction.txt"
            source.write_bytes(instruction_bytes)
            runner = Path(temp) / "run.ps1"
            runner.write_text(self._RUNNER, encoding="utf-8", newline="\n")
            await environment.upload_file(source, "C:/harbor-agent-input/instruction.txt")
            await environment.upload_file(runner, "C:/harbor-agent-input/run.ps1")

        env = self._model_env()
        env["WINDOWS_CLAUDE_WORKDIR"] = self._workdir()
        env["CLAUDE_CONFIG_DIR"] = "C:/logs/agent/sessions"
        command = (
            "powershell.exe -NoLogo -NoProfile -NonInteractive "
            "-ExecutionPolicy Bypass -File C:\\harbor-agent-input\\run.ps1"
        )
        result = await environment.exec(
            command=command,
            cwd=self._workdir(),
            env=env,
            timeout_sec=10800,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if f"INSTRUCTION_UTF8_BYTES={len(instruction_bytes)}" not in output:
            raise RuntimeError("Adapter did not confirm the complete instruction byte count")
        if f"INSTRUCTION_SHA256={instruction_hash}" not in output:
            raise RuntimeError("Adapter did not confirm the complete instruction SHA-256")
        if "EXIT=0" not in output or result.return_code != 0:
            raise RuntimeError(f"Claude Code exited unsuccessfully ({result.return_code})")

        context.metadata = {
            "instruction_utf8_bytes": len(instruction_bytes),
            "instruction_sha256": instruction_hash,
            "adapter_exit": 0,
        }
        self._populate_context_from_stream(output, context)

    @override
    def populate_context_post_run(self, context: AgentContext) -> None:
        path = self.logs_dir / "claude-code.jsonl"
        if not path.is_file():
            return
        input_tokens = output_tokens = cache_tokens = 0
        cost = None
        events = 0
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events += 1
            usage = event.get("usage") if isinstance(event, dict) else None
            if isinstance(usage, dict):
                input_tokens += int(usage.get("input_tokens") or 0)
                output_tokens += int(usage.get("output_tokens") or 0)
                cache_tokens += int(usage.get("cache_read_input_tokens") or 0)
            if isinstance(event, dict) and isinstance(event.get("total_cost_usd"), (int, float)):
                cost = float(event["total_cost_usd"])
        if events:
            context.n_input_tokens = input_tokens
            context.n_output_tokens = output_tokens
            context.n_cache_tokens = cache_tokens
            context.cost_usd = cost
            context.metadata = {**(context.metadata or {}), "stream_events": events}
