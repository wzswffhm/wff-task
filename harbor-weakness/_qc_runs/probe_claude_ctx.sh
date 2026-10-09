#!/bin/bash
# 查 claude-code 是否暴露上下文窗口/自动压缩相关环境变量（决定能否干净修复）
C=gpt56sol4-152v2__env-main-1

echo "=== claude 版本与安装位置 ==="
docker exec "$C" sh -c 'claude --version 2>/dev/null; ls -d /usr/lib/node_modules/@anthropic-ai/claude-code 2>/dev/null || npm root -g 2>/dev/null' 2>&1 | head -5

echo
echo "=== cli 文件 ==="
CLI=$(docker exec "$C" sh -c 'ls /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js 2>/dev/null || find / -maxdepth 6 -name "cli.js" -path "*claude-code*" 2>/dev/null | head -1' 2>/dev/null)
echo "  $CLI"

echo
echo "=== 含 CONTEXT / COMPACT / MAX_TOKEN 的环境变量名 ==="
docker exec "$C" sh -c "grep -oE 'CLAUDE_CODE_[A-Z0-9_]+' $CLI 2>/dev/null | sort -u | head -40" 2>&1

echo
echo "=== 上下文窗口相关标识 ==="
docker exec "$C" sh -c "grep -oE '(contextWindow|context_window|maxOutputTokens|max_output_tokens|MAX_OUTPUT_TOKENS|autoCompact|auto_compact|compactThreshold|CONTEXT_WINDOW)' $CLI 2>/dev/null | sort | uniq -c | head -20" 2>&1

echo
echo "=== 与第三方模型/未知模型相关的开关 ==="
docker exec "$C" sh -c "grep -oE 'ANTHROPIC_[A-Z0-9_]+' $CLI 2>/dev/null | sort -u | head -30" 2>&1

echo
echo "=== 模型元数据来源：fanrenapi /v1/models/gpt-5.6-sol 是否带 context_length ==="
curl -sS --max-time 25 -H "x-api-key: sk-kD3rBDui7Jj4Z1shaFzoMU5l8xjyrbOU99ij4uHrbvmN3UUE" \
  https://fanrenapi.com/v1/models/gpt-5.6-sol 2>&1 | head -c 400
echo
echo "=== 对比：aliyuncs 网关的模型元数据 ==="
curl -sS --max-time 25 -H "x-api-key: sk-ws-H.PREYYHP.VRDq.MEUCIFZhzhwAamdafYFVh3Oc4oo2U2BvIckgxIe849jq3RVmAiEA8bjnEoPt1l7ZKywCo94knr3N60s6pN7U_66HCoZ5EMs" \
  https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic/v1/models 2>&1 | head -c 400
