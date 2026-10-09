# -*- coding: utf-8 -*-
"""探测 lmuai 的 GLM 端点支持哪种协议/鉴权头/模型名，再据此定配置。

背景：glm-5.3 原配 ark 端点（与 Kimi 共 key），ark 5 小时配额在 14:07:32 重置，
用户临时给了 lmuai 的凭据。而 run_model_validation.py 实际调用 call_anthropic()，
由 auth 字段决定请求头（authorization -> Bearer，否则 x-api-key），
必须先确认 lmuai 接受哪种组合，否则会 401/400。

凭据经环境变量 GLM_NEW_KEY 传入，不硬编码、不回显。
用法：set GLM_NEW_KEY=... & python probe_lmuai_glm.py
"""
import httpx
import os
import sys

KEY = os.environ.get("GLM_NEW_KEY", "").strip()
if not KEY:
    print("缺少 GLM_NEW_KEY 环境变量")
    sys.exit(2)
BASE = "https://api.lmuai.com"

MODELS = ["glm-5.3", "GLM-5.3"]

CASES = [
    ("anthropic-x-api-key", f"{BASE}/v1/messages",
     lambda k: {"x-api-key": k, "anthropic-version": "2023-06-01"},
     lambda m: {"model": m, "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}),
    ("anthropic-Bearer", f"{BASE}/v1/messages",
     lambda k: {"authorization": f"Bearer {k}", "anthropic-version": "2023-06-01"},
     lambda m: {"model": m, "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}),
    ("openai-Bearer", f"{BASE}/v1/chat/completions",
     lambda k: {"authorization": f"Bearer {k}"},
     lambda m: {"model": m, "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}),
]

ok = None
for name, url, hf, pf in CASES:
    for model in MODELS:
        try:
            r = httpx.post(url, headers=hf(KEY), json=pf(model), timeout=45)
            body = r.text.replace("\n", " ")[:170]
            mark = "✅" if r.status_code == 200 else "  "
            print(f"{mark} [{name}] model={model:9} -> {r.status_code}  {body}")
            if r.status_code == 200 and ok is None:
                ok = (name, model, url, hf(KEY))
        except Exception as e:  # noqa: BLE001
            print(f"   [{name}] model={model:9} -> ERR {type(e).__name__}: {e}")

if ok:
    name, model, url, headers = ok
    print()
    print("可用组合：")
    print(f"  base_url = {BASE}")
    print(f"  model    = {model}")
    print(f"  组合     = {name}")
    if name.startswith("anthropic"):
        print("  protocol = 'anthropic'（local json 中保持）")
    else:
        print("  protocol = OpenAI 兼容（需把 local json 的 protocol/请求路径改为 openai）")
    auth = "authorization" if "Bearer" in name else "x-api-key"
    print(f"  auth     = {auth}")
else:
    print("\n无组合成功，请确认 key 与模型名")
    sys.exit(1)
