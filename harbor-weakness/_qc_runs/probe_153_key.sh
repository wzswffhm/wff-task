#!/bin/bash
# 验证新 judge/agent 凭据与两个模型在网关上的可用性
GW=$(ip route 2>/dev/null | sed -n 's/^default via \([0-9.]*\).*/\1/p')
export https_proxy="http://$GW:18080" http_proxy="http://$GW:18080"
export no_proxy="localhost,127.0.0.1,::1"

# shellcheck disable=SC1091
set -a; . /mnt/c/Users/Administrator/.wff-creds/judge.env; set +a

for m in qwen3.7-plus qwen3.8-max-0902; do
  echo "=== model=$m ==="
  curl -s -m 60 -o /tmp/resp_$m.json -w 'http_code=%{http_code}\n' \
    "$JUDGE_BASE_URL/v1/messages" \
    -H "x-api-key: $JUDGE_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "content-type: application/json" \
    -d "{\"model\":\"$m\",\"max_tokens\":16,\"messages\":[{\"role\":\"user\",\"content\":\"reply with the single word: ok\"}]}"
  head -c 300 /tmp/resp_$m.json; echo
done
