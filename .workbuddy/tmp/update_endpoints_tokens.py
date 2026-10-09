# -*- coding: utf-8 -*-
"""给 model_endpoints.local.json 补 per-endpoint 输出预算与 extra_body。

依据历史 env 备份（deliverables/2026-10-06_win-rerun-epoch/scripts_backup/env.local.pre_lmuai）：
    QWEN_MAX_TOKENS=65536  OPUS_MAX_TOKENS=64000  GLM_MAX_TOKENS=65536  KIMI_MAX_TOKENS=32000
    KIMI_EXTRA_JSON={"thinking":{"type":"disabled"}}

脚本侧支持（run_model_validation.py:400 / agent_harness.py:463 读 ep["max_tokens"]、ep["extra_body"]），
默认 8192 会把 Qwen 的 thinking 截断（实测 step6 stop=max_tokens out_tok=8192 -> 无产出）。
"""
import json
import pathlib

P = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\skills\harbor-windows\scripts\model_endpoints.local.json")
TOKENS = {"qwen3.8-max": 65536, "opus-5": 64000, "glm-5.3": 65536, "kimi-k3": 32000}
EXTRA = {"kimi-k3": {"thinking": {"type": "disabled"}}}

data = json.loads(P.read_text(encoding="utf-8"))
for ep in data["endpoints"]:
    key = ep["key"]
    ep["max_tokens"] = TOKENS.get(key, 8192)
    if key in EXTRA:
        ep["extra_body"] = EXTRA[key]
    print(f"  {key:14} max_tokens={ep['max_tokens']:<6} extra_body={ep.get('extra_body', '-')}")

P.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"已写入 {P.name}")
