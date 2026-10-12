"""诊断模型端点的凭据可用性。只打印密钥指纹，不打印明文。

用法：python probe_keys.py <endpoint_key> [<endpoint_key> ...]
"""
import hashlib
import json
import os
import sys

SCRIPTS = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\skills\harbor-windows\scripts"
CFG = r"C:\Users\Administrator\Desktop\wff-task\models.local.json"
sys.path.insert(0, SCRIPTS)

import run_model_validation as R  # noqa: E402


def fp(key):
    if not key:
        return None
    return "sha256:%s len=%d" % (hashlib.sha256(key.encode("utf-8")).hexdigest()[:10], len(key))


def main():
    wanted = sys.argv[1:] or ["qwen3.8-max"]
    cfg = json.load(open(CFG, encoding="utf-8"))
    cfg_eps = cfg["endpoints"] if isinstance(cfg, dict) else cfg
    for w in wanted:
        print("=" * 70)
        print("endpoint key = %s" % w)
        cands = []
        hit = [e for e in cfg_eps if e.get("key") == w]
        if hit:
            cands.append(("config", hit[0]))
        hit = [e for e in R.DEFAULT_ENDPOINTS if e.get("key") == w]
        if hit:
            cands.append(("builtin", hit[0]))
        for name, ep in cands:
            env_name = ep.get("api_key_env") or ""
            env_set = bool(os.environ.get(env_name)) if env_name else False
            key = R.get_api_key(ep)
            print("  [%s]" % name)
            print("    base_url   = %s" % ep.get("base_url"))
            print("    model      = %s" % ep.get("model"))
            print("    auth       = %s" % ep.get("auth"))
            print("    api_key_env= %s (%s)" % (env_name, "SET in env" if env_set else "not set"))
            print("    effective key = %s" % fp(key))
            if not key:
                print("    -> no key, skipped")
                continue
            ok, status, text, meta = R.call_anthropic(
                ep["base_url"], key, ep["model"], "Reply with exactly: OK",
                ep.get("auth", "x-api-key"), max_tokens=32)
            print("    -> ok=%s status=%s" % (ok, status))
            print("       body: %s" % (text or "")[:200].replace("\n", " "))
            if meta:
                for k in ("failure_kind", "error", "elapsed"):
                    if k in meta:
                        print("       %s=%s" % (k, meta[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
