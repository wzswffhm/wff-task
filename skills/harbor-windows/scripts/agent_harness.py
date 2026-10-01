# -*- coding: utf-8 -*-
"""agent_harness.py —— harbor-windows 模型调用层的工具化执行环境

## 为什么需要它

规范 8.3 要求被测模型能"正常进入、读取和修改工作区"；SKILL 第 0 步冻结基线中
还包含 **Harness 版本** 与 **工具权限 / 网络策略**。若把 instruction.md 作为
单轮 prompt 直接发出，模型看不到任何源码，只能回复"我需要先查看代码结构"，
无法产出可判分的补丁 —— 这是实测复现过的失败模式，不是模型能力问题。

## 本模块提供

* 受限工作区沙箱：本机临时目录，宿主本身即"真实 Windows Runtime"（不依赖 Docker）
* Anthropic Messages 协议的工具集：``list_files`` / ``read_file`` / ``write_file`` /
  ``run_command`` / ``submit``
* 多轮 tool-use 循环：模型自行探索代码 → 修改文件 → 提交
* 结束后用 ``git diff`` 收集候选补丁，并保留完整轨迹（``trajectory.jsonl``）

## 分工边界

本模块属于**模型调用与记录层**，只负责让模型见到工作区、改动工作区并留下补丁与轨迹。
它**不负责**在真实 Windows Runtime 中执行 F2P/P2P —— 那仍由判分层
（``tests/test.ps1`` + ``tests/grade.py``，或本机等价实现 ``l2_runner.py``）完成，
以守住"不得用 Linux Mock 替代真实 Windows Runtime 验证"的红线。
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import tempfile
import time

import httpx

# ------------------------------------------------------------------ 配置

AGENT_MAX_STEPS = int(os.environ.get("HARBOR_WINDOWS_AGENT_MAX_STEPS", "40"))
AGENT_CMD_TIMEOUT = int(os.environ.get("HARBOR_WINDOWS_AGENT_CMD_TIMEOUT", "300"))
AGENT_REQ_TIMEOUT = float(os.environ.get("HARBOR_WINDOWS_AGENT_REQ_TIMEOUT", "900"))
AGENT_STEP_RETRIES = int(os.environ.get("HARBOR_WINDOWS_AGENT_STEP_RETRIES", "2"))
AGENT_MAX_OBS_CHARS = int(os.environ.get("HARBOR_WINDOWS_AGENT_MAX_OBS", "24000"))
AGENT_MAX_WRITE_CHARS = int(os.environ.get("HARBOR_WINDOWS_AGENT_MAX_WRITE", "400000"))

SANDBOX_ROOT = os.environ.get(
    "HARBOR_WINDOWS_AGENT_SANDBOX",
    os.path.join(os.environ.get("TEMP", "/tmp"), "wff-agent"),
)

# 明显的越界/破坏性命令片段（不追求完备，只挡常见误操作）
_CMD_DENY = (
    "format ", "rd /s", "rd/s", "rmdir /s", "del /f /s", "del /s", "shutdown",
    "/q /c rd", "cipher /w", "diskpart", "bcdedit", "takeown", "icacls c:\\ ",
    "net user", "net localgroup", "reg delete hklm", "curl http", "wget http",
    "invoke-webrequest", "iwr ", "start-process", "powershell -", "> c:\\",
)


# ------------------------------------------------------------------ 工具定义

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


# ------------------------------------------------------------------ 沙箱与工具实现

def _norm(root: str, rel: str) -> str:
    """把相对路径解析进沙箱，拒绝越界。"""
    rel = (rel or ".").replace("\\", "/").strip()
    if rel.startswith("/"):
        rel = rel.lstrip("/")
    p = os.path.normpath(os.path.join(root, rel))
    if p != root and not p.startswith(root + os.sep):
        raise ValueError("路径越界：%s" % rel)
    return p


def _t_list_files(sb: str, a: dict) -> str:
    base = _norm(sb, a.get("path") or ".")
    depth_max = int(a.get("max_depth") or 6)
    if not os.path.isdir(base):
        return "错误：不是目录 —— %s" % (a.get("path") or ".")
    out = []
    base_depth = base.rstrip(os.sep).count(os.sep)
    for cur, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache")]
        d = cur.rstrip(os.sep).count(os.sep) - base_depth
        if d >= depth_max:
            dirs[:] = []
        for f in sorted(files):
            out.append(os.path.relpath(os.path.join(cur, f), sb).replace("\\", "/"))
    return "\n".join(sorted(out)) or "(空)"


def _t_read_file(sb: str, a: dict) -> str:
    p = _norm(sb, a["path"])
    if not os.path.isfile(p):
        return "错误：文件不存在 —— %s" % a["path"]
    if os.path.getsize(p) > 400_000:
        return "错误：文件过大（>400KB），请改用 run_command 查看片段"
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _t_write_file(sb: str, a: dict) -> str:
    content = a.get("content") or ""
    if len(content) > AGENT_MAX_WRITE_CHARS:
        return "错误：内容过大（%d 字符）" % len(content)
    p = _norm(sb, a["path"])
    os.makedirs(os.path.dirname(p) or sb, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    return "已写入 %s（%d 字符）" % (a["path"], len(content))


def _taskkill_tree(pid: int) -> None:
    """尽力终止整棵进程树；失败不抛异常（调用方还有 kill 兜底）。"""
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(int(pid))],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=60)
    except Exception:
        pass


def _run_command_captured(cmd: str, cwd: str, timeout: float):
    """执行 shell 命令并回收输出，返回 (returncode, 合并输出, timed_out)。

    ★ 输出必须重定向到**临时文件**，不能用管道。
    `subprocess.run(capture_output=True, timeout=...)` 在 Windows 上有致命陷阱：
    被执行的命令若留下持有 stdout 管道的后代进程（例如 `python x.py` 内部又拉起了
    后台子进程），超时分支里 CPython 会调用**不带超时的** `communicate()` 去回收，
    而管道 EOF 要等所有继承写端的后代退出 —— 于是永久挂死。
    实测表现：worker 进程 6 秒内 CPU 增量恒为 0.000s、无活动 TCP、轨迹静默数十分钟，
    且**永不自我恢复**（qwen 曾因此卡死 16 分钟，只能整片重启）。

    重定向到文件后没有管道 EOF 语义，`wait(timeout)` 超时即可靠返回；
    再用 `taskkill /F /T` 连整棵树一起收掉，避免留下游离后代污染后续用例。
    """
    fd, out_path = tempfile.mkstemp(prefix="wff-cmd-", suffix=".log")
    os.close(fd)
    timed_out = False
    proc = None
    try:
        with open(out_path, "wb") as sink:
            proc = subprocess.Popen(cmd, shell=True, cwd=cwd,
                                    stdin=subprocess.DEVNULL,
                                    stdout=sink, stderr=subprocess.STDOUT)
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _taskkill_tree(proc.pid)
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    rc = proc.wait(timeout=30)
                except Exception:
                    rc = -1
            finally:
                if proc.poll() is None:
                    _taskkill_tree(proc.pid)
        with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        return rc, body, timed_out
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def _t_run_command(sb: str, a: dict) -> str:
    cmd = (a.get("command") or "").strip()
    if not cmd:
        return "错误：空命令"
    low = cmd.lower()
    for bad in _CMD_DENY:
        if bad in low:
            return "拒绝执行：命令包含被禁止的片段 %r" % bad
    try:
        rc, body, timed_out = _run_command_captured(cmd, sb, AGENT_CMD_TIMEOUT)
    except Exception as e:
        return "错误：%s: %s" % (type(e).__name__, e)
    body = (body or "").strip()
    if timed_out:
        return ("错误：命令超时（>%ds），已终止其进程树。\n%s"
                % (AGENT_CMD_TIMEOUT, body[:4000] or "(无输出)"))
    return "退出码 %d\n%s" % (rc, body or "(无输出)")


def _exec_tool(sb: str, name: str, args: dict) -> str:
    try:
        if name == "list_files":
            return _t_list_files(sb, args)
        if name == "read_file":
            return _t_read_file(sb, args)
        if name == "write_file":
            return _t_write_file(sb, args)
        if name == "run_command":
            return _t_run_command(sb, args)
        if name == "submit":
            return "已提交。"
        return "错误：未知工具 %s" % name
    except Exception as e:
        return "工具执行异常：%s: %s" % (type(e).__name__, e)


# ------------------------------------------------------------------ HTTP

def _git(args, cwd):
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "core.longpaths=true",
         "-c", "user.name=wfflab", "-c", "user.email=wfflab@local",
         "-c", "commit.gpgsign=false"] + args,
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _post(url, headers, payload, timeout=AGENT_REQ_TIMEOUT):
    """流式发送 Anthropic Messages 请求，返回 (status, doc, raw)。

    为什么用流式：GLM-5.3 的 thinking 与部分供应商的长响应是**非流式一次性返回**，
    生成期间连接上没有任何数据，会触发 read timeout（实测 300s/900s 都会被判超时），
    表现为"agent 卡住"。改用 SSE 后数据持续到达，read timeout 只在**两次数据之间**
    计时，长生成不会再被误杀，同时还能实时记录步进度。
    """
    # 流式下 read timeout 是"两次数据到达之间的最大间隔"，给足余量即可。
    to = httpx.Timeout(connect=30.0, read=180.0, write=120.0, pool=60.0)
    if isinstance(timeout, (int, float)):
        to = httpx.Timeout(connect=30.0, read=float(timeout), write=120.0, pool=60.0)

    body = dict(payload)
    body["stream"] = True

    blocks: dict[int, dict] = {}
    stop_reason = None
    usage: dict = {}
    model_returned = None

    with httpx.stream("POST", url, headers=headers, json=body, timeout=to) as r:
        if r.status_code != 200:
            raw = r.read().decode("utf-8", "replace")
            return r.status_code, None, raw

        for line in r.iter_lines():
            if not line:
                continue
            if not line.startswith("data:"):
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
                msg = ev.get("message") or {}
                model_returned = msg.get("model")
                usage.update(msg.get("usage") or {})
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
                dt = d.get("type")
                if dt == "text_delta":
                    blk["text"] = (blk.get("text") or "") + (d.get("text") or "")
                elif dt == "thinking_delta":
                    blk["thinking"] = (blk.get("thinking") or "") + (d.get("thinking") or "")
                elif dt == "input_json_delta":
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

    content = [blocks[i] for i in sorted(blocks)]
    doc = {"content": content, "stop_reason": stop_reason, "usage": usage,
           "model": model_returned}
    return 200, doc, ""


# ------------------------------------------------------------------ 主循环

def system_prompt() -> str:
    return (
        "你是 Harbor Windows 编码任务的执行 Agent。\n"
        "工作区已挂载在沙箱中，你可以用工具浏览、读取和修改其中的文件。\n\n"
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


def run_agent(task_dir: str, ep: dict, run_index: int, instruction: str,
              api_key: str, sandbox_root: str | None = None,
              on_event=None) -> dict:
    """在沙箱中让模型以 agent 方式完成任务，返回结果字典。

    返回字段：
        status / patch / trajectory / steps / meta / sandbox / invalid_reason
    """
    root = sandbox_root or SANDBOX_ROOT
    sb = os.path.join(root, os.path.basename(task_dir.rstrip("/\\")),
                      ep["dir"], "run-%d" % run_index)
    # 干净沙箱
    if os.path.isdir(sb):
        shutil.rmtree(sb, ignore_errors=True)
    os.makedirs(sb, exist_ok=True)

    workspace = os.path.join(task_dir, "environment", "workspace")
    if not os.path.isdir(workspace):
        return {"status": "INVALID", "invalid_reason": "workspace_missing"}

    # 复制工作区内容到沙箱根
    for item in os.listdir(workspace):
        s = os.path.join(workspace, item)
        d = os.path.join(sb, item)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    # 基线提交（补丁收集的锚点）
    _git(["init", "-q"], sb)
    _git(["add", "-A"], sb)
    _git(["commit", "-q", "-m", "baseline"], sb)
    rc = _git(["rev-parse", "HEAD"], sb)
    base_commit = (rc.stdout or "").strip()

    url = ep["base_url"].rstrip("/") + "/v1/messages"
    headers = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
    if ep.get("auth") == "authorization":
        headers["authorization"] = "Bearer " + api_key
    else:
        headers["x-api-key"] = api_key

    messages = [{
        "role": "user",
        "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。",
    }]

    # 轨迹放在 run 专属文件里：并行跑同一模型的多个 run 时不能共用一个文件，
    # 否则两次运行的记录会交错写入，交付材料不可用。
    traj_path = os.path.join(os.path.dirname(sb), "trajectory-run-%d.jsonl" % run_index)
    traj = open(traj_path, "w", encoding="utf-8")

    def log(obj):
        obj["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        traj.write(json.dumps(obj, ensure_ascii=False) + "\n")
        traj.flush()
        if on_event:
            on_event(obj)

    meta = {
        "mode": "agent",
        "agent_max_steps": AGENT_MAX_STEPS,
        "tools": [t["name"] for t in TOOLS],
        "sandbox": sb,
        "base_commit": base_commit,
        "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    steps = 0
    submitted = False
    submit_summary = None
    stop_reason = None
    total_out = 0
    total_in = 0
    t0 = time.time()

    try:
        for step in range(1, AGENT_MAX_STEPS + 1):
            steps = step
            payload = {
                "model": ep["model"],
                "max_tokens": ep.get("max_tokens") or 8192,
                "system": system_prompt(),
                "messages": messages,
                "tools": TOOLS,
            }
            if ep.get("extra_body"):
                payload.update(ep["extra_body"])

            # 按端点可配超时：某些中转/供应商在长上下文 + tools 组合下会静默挂起，
            # 给它们更短的阈值以便快速失败重试，而不是干等十几分钟。
            req_to = float(ep.get("request_timeout") or AGENT_REQ_TIMEOUT)
            last_err = None
            status = doc = raw = None
            for attempt in range(1, AGENT_STEP_RETRIES + 1):
                try:
                    status, doc, raw = _post(url, headers, payload, timeout=req_to)
                    last_err = None
                    break
                except Exception as e:
                    last_err = "%s: %s" % (type(e).__name__, str(e)[:200])
                    log({"step": step, "kind": "transport_retry",
                         "attempt": attempt, "error": last_err})
                    if attempt < AGENT_STEP_RETRIES:
                        time.sleep(min(2 ** attempt, 10))

            if last_err:
                return {**meta, "status": "INVALID",
                        "invalid_reason": "transport_error: %s" % last_err,
                        "steps": steps}

            if status != 200 or doc is None:
                log({"step": step, "kind": "http_error", "status": status, "body": (raw or "")[:1500]})
                return {**meta, "status": "INVALID",
                        "invalid_reason": "http_%s: %s" % (status, (raw or "")[:300]),
                        "steps": steps, "http_status": status}

            blocks = doc.get("content") or []
            usage = doc.get("usage") or {}
            total_in = usage.get("input_tokens") or total_in
            total_out += usage.get("output_tokens") or 0
            stop_reason = doc.get("stop_reason")
            texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
            tool_uses = [b for b in blocks if b.get("type") == "tool_use"]

            log({"step": step, "kind": "assistant", "stop_reason": stop_reason,
                 "text": "\n".join(texts)[:4000],
                 "tool_uses": [{"id": b.get("id"), "name": b.get("name"), "input": b.get("input")}
                               for b in tool_uses],
                 "output_tokens": usage.get("output_tokens")})

            # 把 assistant 回合原样回灌（Anthropic 协议要求保留 tool_use 块）
            messages.append({"role": "assistant", "content": blocks})

            if not tool_uses:
                # 模型停止调用工具 —— 认为它已结束
                log({"step": step, "kind": "stop_without_submit", "stop_reason": stop_reason})
                break

            results = []
            for b in tool_uses:
                name = b.get("name")
                args = b.get("input") or {}
                if name == "submit":
                    submitted = True
                    submit_summary = args.get("summary")
                    obs = "已提交。"
                else:
                    obs = _exec_tool(sb, name, args)
                if len(obs) > AGENT_MAX_OBS_CHARS:
                    obs = obs[:AGENT_MAX_OBS_CHARS] + "\n...(已截断)"
                log({"step": step, "kind": "tool_result", "tool_use_id": b.get("id"),
                     "name": name, "observation": obs[:4000]})
                results.append({"type": "tool_result", "tool_use_id": b.get("id"),
                                "content": obs})
            messages.append({"role": "user", "content": results})

            if submitted:
                break
    finally:
        traj.close()
        meta["elapsed"] = round(time.time() - t0, 2)

    # ---------- 收集补丁 ----------
    _git(["add", "-A"], sb)
    d = _git(["diff", "--cached", "--binary", "--no-color"], sb)
    patch = d.stdout or ""
    # 排除轨迹文件本身
    patch = "\n".join(ln for ln in patch.splitlines()
                      if "trajectory.jsonl" not in ln) + ("\n" if patch else "")

    meta.update({
        "completed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "steps": steps,
        "submitted": submitted,
        "submit_summary": submit_summary,
        "last_stop_reason": stop_reason,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "patch_bytes": len(patch),
    })
    status_final = "VALID" if (submitted or patch.strip()) else "INVALID"
    if status_final == "INVALID":
        meta["invalid_reason"] = "agent_produced_no_change"
    return {**meta, "status": status_final, "patch": patch, "trajectory": traj_path}
