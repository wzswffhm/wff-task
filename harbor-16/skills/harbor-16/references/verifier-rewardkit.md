# Verifier + Reward Kit（harbor-skill）

Pin：`harbor-rewardkit==0.1.4`（若当批文档升级 pin，以文档为准，全题统一）。  
另见 [notes-22.md](notes-22.md)（钉版本、`--ctrf`、`test_outputs.py`）。

## Dockerfile 必备

- 安装 `curl`、`python3`，以及项目构建依赖
- **apt / npm / node / PyPI 默认国内镜像**，详见 [pitfalls.md](pitfalls.md)
- 安装 `uv`/`uvx`
- **扩展包全部 `==` 钉版本**（注意事项 a），至少：
  - `pytest==8.4.1`
  - `pytest-json-ctrf==0.3.5`
  - `harbor-rewardkit==0.1.4`（或以当批文档为准）
  - 若预装：`mini-swe-agent`、`litellm[proxy]` 也必须钉版本（见 notes-22）
- build 期预热：

```bash
uvx --from harbor-rewardkit==0.1.4 rewardkit --help
```

- 只 `COPY workspace/`

```dockerfile
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=UTF-8
```

## test.sh 模式

确定性检查短路 + **`--ctrf`** + 通过后 rewardkit。程序化文件名：**`test_outputs.py`**（不要 `checks.py`）。

```bash
#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier

if ! python3 -m pytest -q /tests/test_outputs.py --ctrf /logs/verifier/ctrf.json; then
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

uvx --from harbor-rewardkit==0.1.4 rewardkit /tests
# 若当批要求 60/40，在此显式聚合后写 reward.txt
```

注意：

- 不要先 standalone 写 `reward.txt` 再调 rewardkit 却不读回结果。
- Judge 鉴权失败、缺 `uvx`、toml 坏掉 = **基础设施失败**，不要当成题目 `reward=0`。
- `reasoning_effort = "none"`；judge 用已验证的 `anthropic/qwen3-max`（或当批文档指定模型）。

## quality.toml 要求

- 必须有 `[judge].judge`、`files` 指向 Agent 工作区真实路径
- 至少两条 `[[criterion]]`，description 绑定本题行为，禁止万能套话
- `[scoring] aggregation = "weighted_mean"` 为默认稳妥选择
- **禁止** 仅 `[quality] version = 1` 空壳

## Oracle 验收

Oracle `reward=1` 时：

- programmatic 通过且存在 `/logs/verifier/ctrf.json`
- quality / judge 路径有执行痕迹
- 缺 quality 分量 → Oracle 门未过，不得进难度门
