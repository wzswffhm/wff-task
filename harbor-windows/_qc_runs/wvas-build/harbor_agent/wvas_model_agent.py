# -*- coding: utf-8 -*-
"""wvas_model_agent.py —— 在 Harbor Windows 容器里跑候选模型的宿主侧 agent。

为什么要自己写：wfflab__wvas-216 的镜像是离线最小镜像（Python embed + MinGit），
没有 Node，也没有网络；Harbor 内置的那些 CLI agent（claude-code / qwen-code /
kimi-cli…）在容器里装不起来。所以把 agent 主循环放在**宿主**侧，模型用 HTTP 调，
工具（读/写文件、跑命令）通过 ``environment.exec`` / ``upload_file`` / ``download_file``
落到容器内执行 —— 与 216 的 outside-harbor runner 同一思路，但产出 Harbor 原生 job。

用法（harbor CLI）：

    PYTHONPATH=<agent 目录> harbor run --path <task> \
      --agent wvas_model_agent:WindowsCodingModelAgent \
      --model claude-opus-5 \
      --ak alias=opus --ak base_url=https://4router.net --ak auth=x-api-key \
      --ak api_key_env=OPUS_API_KEY --ak max_tokens=32000 ...

API key 只从宿主环境变量读（``api_key_env``），不落盘、不进容器。
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import override

import httpx

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

TOOLS = [
    {
        "name": "list_files",
        "description": "列出工作区内的文件与目录（递归，返回相对路径）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作区的目录，默认 '.'"},
                "max_depth": {"type": "integer", "description": "最大递归深度，默认 6"},
            },
        },
    },
    {
        "name": "read_file",
        "description": "读取工作区内某个文件的完整内容（UTF-8）。",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "相对工作区的文件路径"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "写入（覆盖或新建）工作区内的文件。必须给出完整内容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作区的文件路径"},
                "content": {"type": "string", "description": "文件的完整新内容"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": ("在工作区目录下执行一条 shell 命令并返回标准输出/错误。"
                        "可用于运行测试（如 `python -m pytest tests/ -q`）、查看文件等。"),
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "要执行的命令"}},
            "required": ["command"],
        },
    },
    {
        "name": "submit",
        "description": "完成全部修改后调用，提交你的结果并结束任务。",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string", "description": "你做了哪些修改、为什么"}},
            "required": ["summary"],
        },
    },
]

SYSTEM_PROMPT = (
    "你是 Harbor Windows 编码任务的执行 Agent。\n"
    "工作区已挂载在容器中，你可以用工具浏览、读取和修改其中的文件。\n\n"
    "工作方式：\n"
    "1. 先用 list_files 看清目录结构，再用 read_file 读关键源码，理解现状。\n"
    "2. 定位缺陷后，用 write_file 写入修复后的**完整文件内容**。\n"
    "3. 需要验证时用 run_command 执行一次性命令，例如：\n"
    "   `python -m pytest tests/ -q`、`python -c \"...\"`。\n"
    "4. 全部改完后调用 submit 工具结束任务，并在 summary 里说明改动。\n\n"
    "约束（重要）：\n"
    "- **只修改实现代码**（例如包目录下的 .py）。\n"
    "- **不要创建、修改或删除 tests/ 下的任何文件** —— 评测使用独立的测试套件，"
    "你写的测试不参与评分，只会污染最终补丁。\n"
    "- **不要在仓库内留下调试脚本、临时文件或笔记**（如 debug_*.py、run_*.py、*.tmp）。"
    "临时验证请用 `python -c \"...\"` 一次性执行，或写到系统临时目录。\n"
    "- 不要尝试访问工作区之外的路径。\n"
    "- 保持既有公开接口不变，除非任务明确要求。\n"
)

DENY = ("format ", "rd /s", "rmdir /s", "del /f /s", "shutdown", "diskpart", "bcdedit",
        "takeown", "net user", "reg delete hklm", "curl http", "wget http",
        "invoke-webrequest", "start-process", "> c:\\")

MAX_OBS = 24000
MAX_WRITE = 400000

# 中转端点(4router.net)在上游失败时返回 HTTP 200 + 一条纯文本告警：既不是空
# content，也没有 tool_use。历史上这条文本被当成模型正常收工，于是 Opus 只走
# 5 步就 end_turn，基础设施故障被记成模型 VALID/0。出现即按瞬时故障重试，
# 重试耗尽后抛错，让该 job 直接失败(INVALID)而不是记一个假 0 分。
RELAY_ERROR_MARKERS = (
    "上游模型未返回任何内容",
    "触发了安全策略",
    "上游限流",
    "请重试或简化输入后再试",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WindowsCodingModelAgent(BaseAgent):
    SUPPORTS_WINDOWS: bool = True

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        alias: str | None = None,
        base_url: str | None = None,
        auth: str = "x-api-key",
        api_key_env: str | None = None,
        api_key: str | None = None,
        max_tokens: int = 8000,
        request_timeout: float = 1800.0,
        max_steps: int = 40,
        cmd_timeout: float = 300.0,
        extra_body: str | None = None,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._diag: list[dict] = []
        self.alias = alias or "model"
        self.base_url = (base_url or self._get_env("HARBOR_AGENT_BASE_URL") or "").rstrip("/")
        self.auth = auth
        self.api_key = (api_key
                        or (self._get_env(api_key_env) if api_key_env else None)
                        or self._get_env("HARBOR_AGENT_API_KEY"))
        self.max_tokens = int(max_tokens)
        self.request_timeout = float(request_timeout)
        self.max_steps = int(max_steps)
        self.cmd_timeout = float(cmd_timeout)
        # --ak 传 JSON 时 harbor 会直接解析成 dict；字符串形态也接受。
        if isinstance(extra_body, dict):
            self.extra_body = extra_body
        elif isinstance(extra_body, str) and extra_body.strip():
            self.extra_body = json.loads(extra_body)
        else:
            self.extra_body = {}
        if not self.base_url:
            raise ValueError("agent needs base_url (or HARBOR_AGENT_BASE_URL)")
        if not self.api_key:
            raise ValueError("agent needs an API key via api_key_env/环境变量")

    # ------------------------------------------------------------------ 元信息
    @staticmethod
    @override
    def name() -> str:
        return "wvas-windows-model"

    @override
    def version(self) -> str:
        return "1.0.0"

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        return

    # ------------------------------------------------------------------ HTTP
    def _headers(self) -> dict:
        h = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
        if self.auth == "authorization":
            h["authorization"] = "Bearer " + self.api_key
        else:
            h["x-api-key"] = self.api_key
        return h

    def _post_stream(self, payload: dict) -> dict:
        """流式调 Anthropic Messages；上游偶发返回空内容或瞬时错误时自动重试。"""
        last = None
        for attempt in range(1, 5):
            try:
                last = self._post_stream_once(payload)
            except Exception as exc:  # 瞬时网络/流错误也重试
                last = {"status": 0, "doc": None, "raw": "%s: %s" % (type(exc).__name__, exc)}
            doc = (last or {}).get("doc") or {}
            if (last or {}).get("status") == 200 and (doc.get("content") or []):
                return last
            if attempt < 4:
                time.sleep(2.0 * attempt)
        return last

    def _post_stream_once(self, payload: dict) -> dict:
        """流式调 Anthropic Messages，返回 {status, doc, raw}。"""
        url = self.base_url + "/v1/messages"
        to = httpx.Timeout(connect=30.0, read=self.request_timeout, write=120.0, pool=60.0)
        body = dict(payload)
        body["stream"] = True
        deadline = time.time() + self.request_timeout
        blocks: dict[int, dict] = {}
        stop_reason = None
        usage: dict = {}
        with httpx.stream("POST", url, headers=self._headers(), json=body, timeout=to) as r:
            if r.status_code != 200:
                return {"status": r.status_code, "doc": None,
                        "raw": r.read().decode("utf-8", "replace")}
            for line in r.iter_lines():
                if time.time() > deadline:
                    raise TimeoutError("stream wall-clock limit %.0fs exceeded" % self.request_timeout)
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    ev = json.loads(data)
                except Exception:
                    continue
                et = ev.get("type")
                if et == "message_start":
                    usage.update((ev.get("message") or {}).get("usage") or {})
                elif et == "content_block_start":
                    idx = ev.get("index", 0)
                    blk = dict(ev.get("content_block") or {})
                    if blk.get("type") == "tool_use":
                        blk["_json"] = ""
                    blocks[idx] = blk
                elif et == "content_block_delta":
                    idx = ev.get("index", 0)
                    d = ev.get("delta") or {}
                    blk = blocks.setdefault(idx, {"type": "text", "text": ""})
                    if d.get("type") == "text_delta":
                        blk["text"] = (blk.get("text") or "") + (d.get("text") or "")
                    elif d.get("type") == "input_json_delta":
                        blk["_json"] = (blk.get("_json") or "") + (d.get("partial_json") or "")
                elif et == "content_block_stop":
                    idx = ev.get("index", 0)
                    blk = blocks.get(idx)
                    if blk is not None and "_json" in blk:
                        try:
                            blk["input"] = json.loads(blk["_json"] or "{}")
                        except Exception:
                            blk["input"] = {}
                        blk.pop("_json", None)
                elif et == "message_delta":
                    sr = (ev.get("delta") or {}).get("stop_reason")
                    if sr:
                        stop_reason = sr
                    usage.update(ev.get("usage") or {})
                elif et == "message_stop":
                    break
        return {"status": 200,
                "doc": {"content": [blocks[i] for i in sorted(blocks)],
                        "stop_reason": stop_reason, "usage": usage},
                "raw": ""}

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def _cjoin(workspace: str, rel: str) -> str:
        rel = (rel or ".").replace("/", "\\").lstrip("\\")
        if rel in ("", "."):
            return workspace
        return workspace.rstrip("\\") + "\\" + rel

    async def _exec(self, env: BaseEnvironment, command: str, timeout: float | None = None):
        # Harbor's Windows docker exec already wraps with `cmd /S /C`, so the
        # command must be a bare cmd.exe command line (adding another `cmd /c`
        # breaks /S quote handling and yields "filename ... syntax is incorrect").
        res = await env.exec(command, timeout_sec=int(timeout or self.cmd_timeout))
        self._diag.append({"command": command, "return_code": res.return_code,
                           "stdout": (res.stdout or "")[:400],
                           "stderr": (res.stderr or "")[:400]})
        return res

    async def _run_script(self, env: BaseEnvironment, body: str, timeout: float | None = None):
        """把命令写进容器内的临时 .cmd 再执行。

        为什么：这条链路上（docker exec → cmd /S /C）**双引号会被吃掉**，
        `dir /s /b "C:\\testbed"` 会报 "filename ... syntax is incorrect"，而
        `dir /s /b C:\\testbed` 正常。把命令放进脚本文件，命令行的引号/管道/
        重定向就都不经过那层解析了。
        """
        name = "wff-run-%s.cmd" % uuid.uuid4().hex[:12]
        target = "C:\\Windows\\Temp\\" + name
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, name)
            Path(local).write_text("@echo off\n" + body + "\n", encoding="utf-8",
                                   newline="\r\n")
            await env.upload_file(local, target)
        try:
            res = await env.exec(target, timeout_sec=int(timeout or self.cmd_timeout))
        finally:
            try:
                await env.exec("del /f /q " + target, timeout_sec=30)
            except Exception:  # noqa: BLE001
                pass
        self._diag.append({"script": body[:200], "return_code": res.return_code,
                           "stdout": (res.stdout or "")[:400],
                           "stderr": (res.stderr or "")[:400]})
        return res

    async def _t_list_files(self, env, ws, args) -> str:
        path = self._cjoin(ws, args.get("path") or ".")
        r = await self._run_script(env, 'dir /s /b "%s"' % path, timeout=180)
        out = (r.stdout or "").strip()
        if r.return_code != 0 and not out:
            return "错误：不是目录或不可读 —— %s" % (args.get("path") or ".")
        prefix = ws.rstrip("\\") + "\\"
        lines = []
        for ln in out.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            rel = ln[len(prefix):] if ln.lower().startswith(prefix.lower()) else ln
            lines.append(rel.replace("\\", "/"))
        return "\n".join(sorted(lines)[:800]) or "(空)"

    async def _t_read_file(self, env, ws, args) -> str:
        cpath = self._cjoin(ws, args["path"])
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, "payload.bin")
            try:
                await env.download_file(cpath, local)
            except Exception as e:  # noqa: BLE001
                return "错误：文件不存在或不可读 —— %s (%s)" % (args["path"], type(e).__name__)
            data = Path(local).read_bytes()
        if len(data) > 400_000:
            return "错误：文件过大（%d 字节），请改用 run_command 查看片段" % len(data)
        return data.decode("utf-8", "replace")

    async def _t_write_file(self, env, ws, args) -> str:
        content = args.get("content") or ""
        if len(content) > MAX_WRITE:
            return "错误：内容过大（%d 字符）" % len(content)
        cpath = self._cjoin(ws, args["path"])
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, os.path.basename(cpath.replace("\\", "/")))
            Path(local).write_text(content, encoding="utf-8", newline="\n")
            try:
                await env.upload_file(local, cpath)
            except Exception as e:  # noqa: BLE001
                return "错误：写入失败 —— %s: %s" % (type(e).__name__, str(e)[:200])
        return "已写入 %s（%d 字符）" % (args["path"], len(content))

    async def _t_run_command(self, env, ws, args) -> str:
        cmd = (args.get("command") or "").strip()
        if not cmd:
            return "错误：空命令"
        low = cmd.lower()
        for bad in DENY:
            if bad in low:
                return "拒绝执行：命令包含被禁止的片段 %r" % bad
        r = await self._run_script(env, 'cd /d "%s"\n%s' % (ws, cmd))
        body = ((r.stdout or "") + (r.stderr or "")).strip()
        if len(body) > MAX_OBS:
            body = body[:MAX_OBS] + "\n...(已截断)"
        return "退出码 %d\n%s" % (r.return_code, body or "(无输出)")

    async def _run_tool(self, env, ws, name, args) -> str:
        try:
            if name == "list_files":
                return await self._t_list_files(env, ws, args)
            if name == "read_file":
                return await self._t_read_file(env, ws, args)
            if name == "write_file":
                return await self._t_write_file(env, ws, args)
            if name == "run_command":
                return await self._t_run_command(env, ws, args)
            if name == "submit":
                return "已提交。"
            return "错误：未知工具 %s" % name
        except Exception as e:  # noqa: BLE001
            return "工具执行异常：%s: %s" % (type(e).__name__, str(e)[:300])

    # ------------------------------------------------------------------ 主循环
    @override
    async def run(self, instruction: str, environment: BaseEnvironment,
                  context: AgentContext) -> None:
        env = environment
        r = await self._exec(env, "cd", timeout=60)
        ws = ((r.stdout or "").strip().splitlines() or ["C:\\testbed"])[-1].strip() or "C:\\testbed"

        # 形态自检：确认容器里哪种命令写法可用（诊断用，写入 exec-diag.json）
        for probe in ('dir /b', 'dir /s /b "C:\\testbed"', 'dir /s /b C:\\testbed'):
            try:
                pr = await env.exec(probe, timeout_sec=60)
                self._diag.append({"probe": probe, "return_code": pr.return_code,
                                   "stdout": (pr.stdout or "")[:200],
                                   "stderr": (pr.stderr or "")[:200]})
            except Exception as e:  # noqa: BLE001
                self._diag.append({"probe": probe, "exception": "%s: %s" % (type(e).__name__, e)})
        (self.logs_dir / "exec-diag.json").write_text(
            json.dumps({"workspace": ws, "probes": self._diag[:3]}, ensure_ascii=False, indent=2),
            encoding="utf-8")

        traj_path = self.logs_dir / "trajectory.jsonl"
        traj = traj_path.open("w", encoding="utf-8")

        def log(obj: dict) -> None:
            obj["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            traj.write(json.dumps(obj, ensure_ascii=False) + "\n")
            traj.flush()

        meta = {"alias": self.alias, "model": self.model_name, "workspace": ws,
                "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        log({"step": 0, "kind": "start", **meta})
        # 中文题面进轨迹（新版自检要求轨迹里能看到中文口语化提示）
        log({"step": 0, "kind": "user", "text": instruction[:6000]})

        messages = [{"role": "user",
                     "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。"}]
        submitted = False
        submit_summary = None
        total_in = total_out = 0
        steps = 0
        t0 = time.time()
        stop_reason = None

        try:
            for step in range(1, self.max_steps + 1):
                steps = step
                payload = {"model": self.model_name, "max_tokens": self.max_tokens,
                           "system": SYSTEM_PROMPT, "messages": messages, "tools": TOOLS}
                payload.update(self.extra_body)
                got = None
                last_err = None
                for attempt in range(1, 7):
                    try:
                        got = await asyncio.to_thread(self._post_stream, payload)
                    except Exception as e:  # noqa: BLE001
                        last_err = "%s: %s" % (type(e).__name__, str(e)[:160])
                        log({"step": step, "kind": "transport_retry", "attempt": attempt,
                             "error": last_err})
                        await asyncio.sleep(min(3 * attempt, 20))
                        continue
                    if got["status"] != 200:
                        log({"step": step, "kind": "http_error", "status": got["status"],
                             "body": (got["raw"] or "")[:600]})
                        raise RuntimeError("http_%s: %s" % (got["status"], (got["raw"] or "")[:200]))
                    blocks = (got["doc"] or {}).get("content") or []
                    texts = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
                    tuses = [b for b in blocks if b.get("type") == "tool_use"]
                    relay_error = (not tuses) and any(
                        marker in texts for marker in RELAY_ERROR_MARKERS)
                    # 中转有时返回 output_tokens=1 的"空回复"（stop_reason 为 null），
                    # 用 not output_tokens 判不出来，必须按极小输出量兜底。实测 215 的
                    # Opus#1 就是这样在第 15 步被截断、还被记成 VALID/0。
                    tiny = (not tuses) and int(
                        (got["doc"] or {}).get("usage", {}).get("output_tokens") or 0) < 10
                    empty = relay_error or tiny or (
                        (not tuses) and (not texts.strip()) and not (
                            (got["doc"] or {}).get("usage") or {}).get("output_tokens"))
                    if empty:
                        if attempt < 6:
                            log({"step": step, "kind": "upstream_empty_retry",
                                 "attempt": attempt, "relay_error": relay_error,
                                 "text": texts[:200]})
                            await asyncio.sleep(min(3 * attempt, 20))
                            continue
                        raise RuntimeError(
                            "upstream_empty_after_6_attempts: %s"
                            % (texts[:200].strip() or "<empty>"))
                    break
                if got is None:
                    raise RuntimeError("transport_error: %s" % last_err)

                doc = got["doc"] or {}
                usage = doc.get("usage") or {}
                total_in = usage.get("input_tokens") or total_in
                total_out += usage.get("output_tokens") or 0
                stop_reason = doc.get("stop_reason")
                blocks = doc.get("content") or []
                tuses = [b for b in blocks if b.get("type") == "tool_use"]
                log({"step": step, "kind": "assistant", "stop_reason": stop_reason,
                     "text": "\n".join(b.get("text") or "" for b in blocks
                                       if b.get("type") == "text")[:4000],
                     "tool_uses": [{"name": b.get("name"), "input": b.get("input")}
                                   for b in tuses],
                     "output_tokens": usage.get("output_tokens")})
                messages.append({"role": "assistant", "content": blocks})
                if not tuses:
                    break
                results = []
                for b in tuses:
                    nm = b.get("name")
                    args = b.get("input") or {}
                    if nm == "submit":
                        submitted = True
                        submit_summary = args.get("summary")
                        obs = "已提交。"
                    else:
                        obs = await self._run_tool(env, ws, nm, args)
                    if len(obs) > MAX_OBS:
                        obs = obs[:MAX_OBS] + "\n...(已截断)"
                    log({"step": step, "kind": "tool_result", "name": nm,
                         "observation": obs[:4000]})
                    results.append({"type": "tool_result", "tool_use_id": b.get("id"),
                                    "content": obs})
                messages.append({"role": "user", "content": results})
                if submitted:
                    break
        finally:
            traj.close()

        elapsed = round(time.time() - t0, 2)
        # 容器内改动快照（git diff），便于人工复核
        try:
            d = await self._run_script(env, 'cd /d "%s"\ngit add -A\ngit diff --cached '
                                            '--binary --no-color' % ws, timeout=300)
            if (d.stdout or "").strip():
                (self.logs_dir / "patch.diff").write_text(d.stdout, encoding="utf-8",
                                                          newline="\n")
        except Exception:  # noqa: BLE001
            pass

        here = Path(__file__).resolve()
        model_result = {
            "alias": self.alias,
            "model": self.model_name,
            "label": self.alias,
            "protocol": "anthropic",
            "base_url": self.base_url,
            "auth": self.auth,
            "runner": str(here),
            "runner_sha256": _sha256_file(here),
            "steps": steps,
            "submitted": submitted,
            "submit_summary": submit_summary,
            "input_tokens": total_in,
            "output_tokens": total_out,
            "elapsed_sec": elapsed,
            "last_stop_reason": stop_reason,
            "workspace": ws,
            "trajectory": str(traj_path),
            "completed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        (self.logs_dir / "model-result.json").write_text(
            json.dumps(model_result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        context.n_output_tokens = total_out
        self.logger.info("agent finished: steps=%s submitted=%s out_tokens=%s",
                         steps, submitted, total_out)
