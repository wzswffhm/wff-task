# Harbor任务验证与测试完整指南
```bash
echo 'export OPENAI_API_KEY="sk-ws-H.ERLPMXH.Ri8o.MEUCIEDZStrMawp6trUj2WJNnCCXkFMsNaIC7JqevElHKirvAiEA0T-LiQ6jIKmYgMds8yA4D3auDKMvjrfK6wD0YKoQgP0"' >> ~/.bashrc
echo 'export OPENAI_BASE_URL="https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"' >> ~/.bashrc
echo 'export OPENAI_MODEL="qwen3.8-max"' >> ~/.bashrc
source ~/.bashrc
```

```bash
# Nop就是"No Operation"，表示Agent什么都不改
harbor trials start \
  --path zq20260811000001-block-storage-go-bugfix-20260811-1940 \
  --agent nop \
  --trials-dir zq20260811000001-block-storage-go-bugfix-20260811-1940/jobs/nop
```

```bash
# Oracle就是"神谕"，表示用参考答案跑
harbor trials start \
  --path zq20260811000001-block-storage-go-bugfix-20260811-1940 \
  --agent oracle \
  --trials-dir zq20260811000001-block-storage-go-bugfix-20260811-1940/jobs/oracle
```

```bash
harbor trials start \
  --path file-storage-hard-01/ \
  --agent qwen-coder \
  --model qwen3.8-max \
  --ae OPENAI_API_KEY=$OPENAI_API_KEY \
  --ae OPENAI_BASE_URL=$OPENAI_BASE_URL \
  --agent-timeout 3600 \
  --agent-setup-timeout-multiplier 5 \
  --trials-dir file-storage-hard-01/jobs/smoke

参数说明：~
--agent codex：用哪个Agent（codex是Harbor自带的）
--model qwen3.8-max：用哪个模型
--agent-timeout 3600：Agent最多跑1小时（3600秒）
--trials-dir：结果存哪里
```

```bash
harbor run \
  --path zq20260811000001-block-storage-go-bugfix-20260811-1940/ \
  --agent qwen-coder \
  --model qwen3.8-max \
  --ae OPENAI_API_KEY=$OPENAI_API_KEY \
  --ae OPENAI_BASE_URL=$OPENAI_BASE_URL \
  --n-attempts 16 \
  --n-concurrent 2 \
  --max-retries 3 \
  --agent-timeout-multiplier 10 \
  --agent-setup-timeout-multiplier 5 \
  --job-name zq20260811000001-block-storage-go-bugfix-20260811-1940 \
  --jobs-dir jobs/trials

参数解释：
参数	意思	你的值
--n-attempts	总共跑几次	16
--n-concurrent	同时跑几个	4（看你电脑性能）
--max-retries	失败了重试几次	3
--job-name	这次测试起个名	linux-io-fd-leak-hard-01
--agent-setup-timeout-multiplier启动超时倍数	3
```
