"""Stream Anthropic-compatible requests through the Windows host.

Sidecar-side parameters are read from the relay process environment:

* THINKING_ENABLED / THINKING_MODE / THINKING_BUDGET_TOKENS
* MAX_TOKENS_LIMIT
* MID_SYSTEM_MESSAGE_STRATEGY
"""

from __future__ import annotations

import http.server
import json
import os
import urllib.error
import urllib.request


BASE_URL = os.environ["RELAY_UPSTREAM_URL"].rstrip("/")
PORT = int(os.environ.get("RELAY_PORT", "18182"))
MAX_BODY = 20_000_000
HOP_HEADERS = {"host", "content-length", "connection", "accept-encoding", "transfer-encoding"}
RESPONSE_HOP_HEADERS = {"content-length", "transfer-encoding", "connection", "content-encoding"}


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_int_env(name: str) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _optional_float_env(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


THINKING_ENABLED = _env_flag("THINKING_ENABLED")
THINKING_MODE = os.environ.get("THINKING_MODE", "").strip()
THINKING_BUDGET_TOKENS = _positive_int_env("THINKING_BUDGET_TOKENS")
MAX_TOKENS_LIMIT = _positive_int_env("MAX_TOKENS_LIMIT")
MID_SYSTEM_MESSAGE_STRATEGY = os.environ.get("MID_SYSTEM_MESSAGE_STRATEGY", "").strip().lower()
MODEL_TEMPERATURE = _optional_float_env("MODEL_TEMPERATURE")
MODEL_TOP_P = _optional_float_env("MODEL_TOP_P")
MODEL_TOP_K = _positive_int_env("MODEL_TOP_K")
ENABLE_THINKING = _env_flag("ENABLE_THINKING")
REASONING_EFFORT = os.environ.get("REASONING_EFFORT", "").strip()
DEBUG_LOG = os.environ.get("RELAY_DEBUG_LOG", "").strip()

if DEBUG_LOG:
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as debug_file:
            debug_file.write(
                "RELAY_START "
                f"BASE_URL_LEN={len(BASE_URL)} "
                f"THINKING_ENABLED={THINKING_ENABLED} "
                f"THINKING_MODE={THINKING_MODE} "
                f"THINKING_BUDGET_TOKENS={THINKING_BUDGET_TOKENS} "
                f"MAX_TOKENS_LIMIT={MAX_TOKENS_LIMIT} "
                f"MID_SYSTEM_MESSAGE_STRATEGY={MID_SYSTEM_MESSAGE_STRATEGY}\n"
            )
    except OSError:
        pass


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _prepend_text(content, prefix: str):
    if not prefix:
        return content
    if isinstance(content, str):
        return f"{prefix}\n\n{content}"
    if isinstance(content, list):
        return [{"type": "text", "text": prefix}, *content]
    return prefix


def _merge_system_messages(body: dict) -> dict:
    if MID_SYSTEM_MESSAGE_STRATEGY != "merge":
        return body
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body

    merged: list[dict] = []
    pending: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            merged.append(message)
            continue
        role = message.get("role")
        if role == "system":
            text = _extract_text(message.get("content"))
            if text:
                pending.append(text)
            continue
        if role == "user" and pending:
            message = dict(message)
            message["content"] = _prepend_text(message.get("content"), "\n\n".join(pending))
            pending = []
        merged.append(message)

    if pending and merged:
        for index in range(len(merged) - 1, -1, -1):
            if merged[index].get("role") == "user":
                merged[index] = dict(merged[index])
                merged[index]["content"] = _prepend_text(
                    merged[index].get("content"), "\n\n".join(pending)
                )
                break
    body["messages"] = merged
    return body


def _apply_max_tokens(body: dict) -> dict:
    if MAX_TOKENS_LIMIT <= 0:
        return body
    current = body.get("max_tokens")
    if current is None or (isinstance(current, int) and not isinstance(current, bool) and current > MAX_TOKENS_LIMIT):
        body["max_tokens"] = MAX_TOKENS_LIMIT
    return body


def _apply_thinking(body: dict) -> dict:
    model = str(body.get("model", "")).lower()
    if ENABLE_THINKING and "claude" not in model:
        return body
    if not THINKING_ENABLED:
        return body
    budget = THINKING_BUDGET_TOKENS or 24000
    body["thinking"] = {"type": "enabled", "budget_tokens": budget}
    current = body.get("max_tokens")
    if current is None or (isinstance(current, int) and not isinstance(current, bool) and current <= budget):
        body["max_tokens"] = MAX_TOKENS_LIMIT if MAX_TOKENS_LIMIT > budget else budget + 1
    return body


def _apply_generation_params(body: dict) -> dict:
    model = str(body.get("model", "")).lower()
    if MODEL_TEMPERATURE is not None:
        body["temperature"] = MODEL_TEMPERATURE
    if MODEL_TOP_P is not None:
        body["top_p"] = MODEL_TOP_P
    if MODEL_TOP_K:
        body["top_k"] = MODEL_TOP_K
    if ENABLE_THINKING and "claude" not in model:
        body["enable_thinking"] = True
    if REASONING_EFFORT and "claude" not in model:
        body["reasoning_effort"] = REASONING_EFFORT
    return body


def _transform_body(body: dict) -> dict:
    body = _merge_system_messages(body)
    body = _apply_max_tokens(body)
    body = _apply_thinking(body)
    body = _apply_generation_params(body)
    return body


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        if not self.path.startswith("/v1/messages"):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if not 0 < length < MAX_BODY:
            self.send_error(413)
            return
        if not (self.headers.get("x-api-key") or self.headers.get("Authorization")):
            self.send_error(401)
            return
        if DEBUG_LOG:
            try:
                with open(DEBUG_LOG, "a", encoding="utf-8") as debug_file:
                    debug_file.write(
                        "REQUEST_HEADER_NAMES="
                        + ",".join(sorted(str(key) for key in self.headers.keys()))
                        + "\n"
                    )
            except OSError:
                pass

        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400)
            return
        if not isinstance(payload, dict):
            self.send_error(400)
            return
        body = json.dumps(_transform_body(payload), ensure_ascii=False).encode("utf-8")

        headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP_HEADERS}
        if DEBUG_LOG:
            try:
                with open(DEBUG_LOG, "a", encoding="utf-8") as debug_file:
                    debug_file.write(
                        "OUT_HEADER_NAMES="
                        + ",".join(sorted(str(key) for key in headers.keys()))
                        + "\n"
                    )
            except OSError:
                pass
        request = urllib.request.Request(BASE_URL + self.path, data=body, headers=headers, method="POST")
        try:
            upstream = urllib.request.urlopen(request, timeout=1800)
        except urllib.error.HTTPError as error:
            upstream = error
        except Exception:
            self.send_error(502)
            return

        with upstream:
            self.send_response(upstream.status)
            for key, value in upstream.headers.items():
                if key.lower() not in RESPONSE_HOP_HEADERS:
                    self.send_header(key, value)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                while chunk := upstream.read(8192):
                    self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass


http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
