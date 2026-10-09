#!/bin/bash
# 探活 4router opus 端点
KEY=sk-ABTdFUULEu52VnGHNhWQX8BA13uMpbPdTZZrogR5oGTla2gE
BASE=https://4router.net
echo "=== POST $BASE/v1/messages (claude-opus-4-8) ==="
curl -sS --max-time 40 -X POST "$BASE/v1/messages" \
  -H "content-type: application/json" \
  -H "x-api-key: $KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-opus-4-8","max_tokens":24,"messages":[{"role":"user","content":"reply OK"}]}' \
  2>&1 | head -c 600
echo
echo "=== GET $BASE/v1/models ==="
curl -sS --max-time 25 "$BASE/v1/models" \
  -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" 2>&1 | head -c 400
echo
