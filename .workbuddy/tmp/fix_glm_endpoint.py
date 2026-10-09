# -*- coding: utf-8 -*-
"""修正 model_endpoints.local.json 里 glm-5.3 的 base_url（key 与端点不匹配导致 401）。

历史 env 备份（deliverables/2026-10-06_win-rerun-epoch/scripts_backup/env.local.pre_lmuai）为准：
    GLM_BASE_URL = https://ark.cn-beijing.volces.com/api/coding
    GLM_API_KEY  = ark-9bd3…（46 字符，与 kimi 同一个方舟 key）
    GLM_MODEL    = glm-5.3
    GLM_AUTH     = authorization   -> Bearer
而我生成的 local json 把 base_url 误写成 https://api.lmuai.com，
把方舟的 key 发给了 lmuai 端点 -> HTTP 401 INVALID_API_KEY。

用法：python fix_glm_endpoint.py [--dry-run]
"""
import json
import pathlib
import sys

P = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\skills\harbor-windows\scripts\model_endpoints.local.json")
ARK = "https://ark.cn-beijing.volces.com/api/coding"
dry = "--dry-run" in sys.argv

data = json.loads(P.read_text(encoding="utf-8"))
changed = []
for ep in data["endpoints"]:
    if ep["key"] == "glm-5.3":
        before = ep.get("base_url")
        if before != ARK:
            ep["base_url"] = ARK
            ep.setdefault("auth", "authorization")
            changed.append((before, ARK))

for ep in data["endpoints"]:
    print(f"  {ep['key']:14} {ep.get('base_url'):58} model={ep.get('model')} "
          f"auth={ep.get('auth', '-')} key_prefix={(ep.get('api_key') or '')[:8]}")

if not changed:
    print("\n无需修改（已是 ark 端点）")
elif dry:
    print(f"\n[dry-run] 将修改: {changed}")
else:
    P.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已修正 glm-5.3 base_url: {changed[0][0]} -> {changed[0][1]}")
