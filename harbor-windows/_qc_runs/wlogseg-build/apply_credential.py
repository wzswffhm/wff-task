"""把用户提供的新凭据写入 models.local.json（该文件被 .gitignore 的 *.local.json 忽略）。

密钥经环境变量 WFF_NEW_KEY 传入，不写入本文件。
"""
import hashlib
import json
import os

P = r"C:\Users\Administrator\Desktop\wff-task\models.local.json"
BASE = "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic"

KEY = os.environ["WFF_NEW_KEY"]

cfg = json.load(open(P, encoding="utf-8"))
eps = cfg["endpoints"]
touched = []

for e in eps:
    if e.get("key") == "qwen3.8-max":
        e["base_url"] = BASE
        e["api_key"] = KEY
        e["api_key_env"] = ""
        e["model"] = "qwen3.8-max-0902"
        e["status"] = "active"
        e["note"] = "user-supplied credential 2026-10-12"
        touched.append("qwen3.8-max")

if not any(e.get("key") == "qwen3.7-plus" for e in eps):
    eps.append({
        "key": "qwen3.7-plus", "label": "Qwen3.7-Plus", "name": "Qwen3.7-Plus",
        "dir": "qwen3.7-plus", "model": "qwen3.7-plus", "provider": "aliyun-maas",
        "base_url": BASE, "api_key": KEY, "api_key_env": "", "auth": "x-api-key",
        "protocol": "anthropic-messages", "max_tokens": 65536, "runs": 1,
        "role": "auxiliary", "status": "active",
        "note": "user-supplied credential 2026-10-12",
    })
    touched.append("qwen3.7-plus (added)")

json.dump(cfg, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("updated endpoints: %s" % ", ".join(touched))
print("qwen3.8-max key sha256[:10]=%s len=%d" % (
    hashlib.sha256(KEY.encode()).hexdigest()[:10], len(KEY)))
