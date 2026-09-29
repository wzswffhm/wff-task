# 22 注意事项（培训截图标准）

与 `Coding ENV`「22注意事项」对齐。出题/打包前逐条核对。

## a. 扩展包必须钉死可用版本

任何 pip/uv 扩展包 **禁止浮动最新版**；Dockerfile 重建会从 PyPI 拉最新，上游不兼容会导致与出题时环境不一致、验证不可控。

示例（版本以当批文档为准，全题统一 pin）：

```dockerfile
RUN uv venv /opt/harbor-venv \
 && uv pip install --python /opt/harbor-venv/bin/python \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5 \
      harbor-rewardkit==0.1.4 \
      mini-swe-agent==1.16.0 \
      "litellm[proxy]==1.80.0"
# build 期预热 rewardkit，避免运行时联网
```

`harbor-rewardkit` / `mini-swe-agent` / `litellm` 的具体版本号以当批培训文档代码块为准；**禁止**不写 `==`。

## B. test.sh 必须带 `--ctrf`

- Dockerfile 安装：`pytest-json-ctrf==0.3.5`（钉死）
- `test.sh` 调用 pytest 时加 CTRF 输出，例如：

```bash
pytest /tests/test_outputs.py --ctrf /logs/verifier/ctrf.json
```

（若仍走 rewardkit，确定性 pytest 阶段同样要写 ctrf；路径保持 `/logs/verifier/ctrf.json`。）

## C. macOS 打包前清隐藏文件

打包前删除 `.DS_Store` 等；建议用脚本/`zip -x`/`rsync --exclude` 压缩，避免打进交付包。

## D. tests 目录文件名

注意事项原文：`tests` 下只放 **`test_outputs.py`** 与 **`test.sh`**，**不要放 `checks.py`**。

本标注流额外要求（质检 P0）：还须有真实 **`quality.toml`** 且 `test.sh` 接入 rewardkit。  
因此执行口径：

- 程序化验文件命名为 **`test_outputs.py`**（禁止再叫 `checks.py`）
- 保留 **`quality.toml`**
- `test.sh`：pytest `test_outputs.py`（含 `--ctrf`）+ rewardkit

## E. jobs 目录需要上传

上传 zip **必须含 `jobs/`**，且质检会核对 baseline/oracle 是否存在（smoke 不强制）。

结合本 skill 打包规则：先全量本地备份；上传包里 `jobs/` **必须含**：

- `baseline` 或 `nop`
- `oracle`
- 最终成功难度门（一个）

`*smoke*` **可选**（跑过可带；未跑不要求）。  
失败 rounds / `_full_job_backups` 等不进上传包。  
**禁止**只交难度门（缺 baseline/oracle 会挂）；**不要**为凑包强行补跑 smoke。

## F. Base URL 与模型

| 用途 | 值 |
|------|-----|
| OpenAI 兼容 | `https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |
| Anthropic 兼容 | `https://dashscope.aliyuncs.com/apps/anthropic` |
| 模型 | `qwen3.8-max` |

只通过环境变量 / `--ae` 注入；不写进任务文件或 zip。

## G. 提示词不要有 AI 痕迹

见 SKILL「提示词禁止 AI 痕迹」与 [instruction-style.md](instruction-style.md)。

## H. 同项目多题

同一仓库可出多道题，但 **不要打同一模块**；提示词质量要高（具体、可验、无 AI 腔）。

## I. 任务类型贴合提示词

飞书 / `task.toml` 的 `task_type`（feature / bug-fix 等）必须与 `instruction.md` 实际在做的事一致，禁止文不对题。
