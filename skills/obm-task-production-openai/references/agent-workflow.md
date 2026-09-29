# Seed API 对照实验

本文件适用于 DeepSWE 题目完成正式包和 NOP/Oracle 验证后的 Agent 实验。实验通过 OpenAI 兼容接口调用 `doubao-seed-evolving`，只走本地后台脚本和 Docker。禁止调用 MCP、Computer Use、浏览器、桌面软件、IDE、Trae 或其他图形界面；这里的流程不能与同目录的 `obm-task-production`（非 OpenAI 版）混用。

## 运行前提

项目根目录的 `model.env` 使用 `KEY=value` 格式：

```text
key=API 密钥
url=OpenAI 兼容接口地址
```

也可以使用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。配置文件不得复制进题包、Agent 工作区、运行轨迹或上传材料。运行脚本依赖见 `scripts/requirements-seed.txt`。

项目虚拟环境必须优先使用；只有没有项目虚拟环境时才回退到`python3`。Windows 下解释器在`.venv/Scripts/python.exe`，Linux/macOS 在`.venv/bin/python`。首次准备环境时可执行：

```bash
uv venv .venv
uv pip install --python .venv/Scripts/python.exe \
  -r "$OBM_SKILL_DIR/scripts/requirements-seed.txt"
OBM_PYTHON=./.venv/Scripts/python.exe
```

（Linux/macOS 把上述路径换成`.venv/bin/python`。）

如果`.venv`已经存在，不要重建，只需用`uv pip install`指向既有解释器检查并补齐依赖。

正式实验前必须满足：

- proposal、参考实现和 verifier 已定稿；
- NOP `reward=0`，Oracle `reward=1`；
- `sources/skill/SKILL.md` 已通过中文检查；
- Docker 可用，app 和 verifier 镜像能在 `--network=none` 下构建；
- 两侧使用相同模型、推理强度、轮次上限、token 上限和工具权限。

## 目录结构

`agent-runs` 是内部验证材料，不进入正式提交包：

```text
agent-runs/
  no-skill/
    repo/
    PROMPT.md
    RUN_RECORD.md
    seed-output/
      PROGRESS.json
      API_RUN.json
      TRANSCRIPT.jsonl
      FINAL_RESPONSE.md
      model.patch
    verification/
      VERIFICATION.json
      APP_BUILD.log
      VERIFIER_BUILD.log
      VERIFIER_RUN.log
      logs/
  with-skill/
    repo/
    PROMPT.md
    RUN_RECORD.md
    seed-output/
    verification/
  BASELINE.json
  BACKGROUND_RUN.json
  BACKGROUND_MONITOR.log
  EXPERIMENT_PROGRESS.json
  MONITOR_STATUS.jsonl
  SEED_EXPERIMENT.log
  SEED_COMMAND_IMAGE.log
  EXPERIMENT_RESULT.json
  TURN_STATS.json
  FINALIZATION_RESULT.json
```

`repo` 是模型唯一可以读写的工作区。`PROMPT.md` 放在仓库外，避免进入 patch。with-skill 的提示词包含正式包中完整的中文专家 skill；no-skill 不含专家经验。

## 准备并执行

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/prepare_agent_runs.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-name \
  --run-root ./work/YYYY-MM-DD-N-name/agent-runs-v1 \
  --run-seed \
  --env-file ./model.env \
  --model doubao-seed-evolving \
  --reasoning-effort minimal \
  --max-turns 120 \
  --poll-seconds 300 \
  --target-no-skill-min-turns 101 \
  --target-with-skill-turns 70 \
  --target-with-skill-tolerance 10
```

准备脚本从 `sources/app/upstream.tar.gz` 创建两套仓库，并用相同作者、提交时间和提交信息初始化 Git。它必须确认：

- 两边的基线 HEAD 相同；
- 初始工作树为空；
- 排除 `.git` 后文件树相同；
- `BASELINE.json` 记录 upstream、proposal、skill、任务契约和两份提示词散列；
- 目标目录已存在时停止，不覆盖旧运行。

## Seed 工具边界

`run_seed_agent.py` 通过 OpenAI Python SDK 调用模型，并提供列文件、读文件、搜索、写文件、应用补丁、执行命令和查看 diff 的工具。

文件工具解析真实路径后必须位于当前 `repo`。命令工具不在宿主机 shell 中直接执行，而是在题目的 app Docker 镜像中运行：

- `--network=none`；
- 只把当前 `repo` 挂载到 `/app`；
- 不挂载 `model.env`、正式题包、verifier 或另一侧工作区；
- 不把 API key 或 URL 写入容器环境；
- 禁止安装依赖、访问远端和修改远端 Git；
- verifier 在 Agent 结束后单独运行，模型看不到私有失败详情。

Seed 自己声称测试通过不能作为结果。`verify_agent_patch.py` 从 `model.patch` 构建独立禁网 verifier，只有 `VERIFICATION.json` 的 `reward` 有效。

## 定时监听与轮次统计

`prepare_agent_runs.py --run-seed` 默认调用 `launch_seed_background.py`，在独立会话中启动监控器后立即返回。当前 Codex 回合不得一直等待后台进程。如果运行目录已经准备好但尚未启动，使用：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/launch_seed_background.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-name \
  --run-root ./work/YYYY-MM-DD-N-name/agent-runs-v1 \
  --env-file ./model.env \
  --model doubao-seed-evolving \
  --max-turns 120 \
  --poll-seconds 300 \
  --target-no-skill-min-turns 101 \
  --target-with-skill-turns 70 \
  --target-with-skill-tolerance 10 \
  --finalize-on-pass
```

后台启动器保存：

- `BACKGROUND_RUN.json`：PID、启动时间、监控命令、日志路径和精简状态命令；
- `BACKGROUND_MONITOR.log`：后台监控器的标准输出和错误输出。

后台启动成功后，监控器按 `--poll-seconds` 自己定时读取状态；生产默认值为 300 秒（5 分钟），no-skill 和 with-skill 必须使用同一个间隔。状态写入 `MONITOR_STATUS.jsonl`、`EXPERIMENT_PROGRESS.json` 和 `TURN_STATS.json`。不创建客户端 heartbeat、automation、MCP 调用或其他对话定时任务；不打开任何桌面软件。需要人工查看时只运行一次下面的精简状态命令，不读取完整日志：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/inspect_seed_status.py" \
  --run-root ./work/YYYY-MM-DD-N-name/agent-runs-v1
```

后台监控器先用 `docker info` 确认 Docker 可用，再启动顺序实验。它每隔 `poll-seconds` 秒读取：

- `EXPERIMENT_PROGRESS.json`：命令镜像构建、no-skill Agent、no-skill verifier、with-skill Agent、with-skill verifier 或最终状态；
- 两侧 `seed-output/PROGRESS.json`：当前轮次、工具调用数、最后事件和耗时；
- `API_RUN.json` 与 `VERIFICATION.json`：Agent 完成和 verifier reward；
- `EXPERIMENT_RESULT.json`：最终状态。

每次本地轮询追加到 `MONITOR_STATUS.jsonl`，子进程标准输出写入 `SEED_EXPERIMENT.log`；这些轮询在后台 Python 进程内完成，不调用 Codex。实验结束后生成 `TURN_STATS.json`，至少记录两侧轮次、reward、严格验收结果和轮次偏好命中情况。`--timeout-seconds 0` 表示监控器不额外设置总时限；指定非零超时后，超时属于基础设施错误，不能计作 no-skill 失败。`--finalize-on-pass` 默认启用：严格对照通过后自动执行最终质检、仪表盘截图和 ZIP 打包；可用 `--no-finalize-on-pass` 仅在调试监控器时关闭。

默认轮次偏好：

- no-skill：至少 101 轮；
- with-skill：接近 70 轮，默认容差为 ±10，即 60–80 轮。

轮次偏好不是验收门槛。Agent 正常完成后不得继续空转，不能插入无意义命令、隐藏停止信号或改变工具协议来凑轮次。未命中偏好时保留真实结果，并把它作为题目难度和专家 skill 篇幅的调优信号。

## 顺序状态机

`run_seed_experiment.py` 必须按以下顺序运行：

1. 构建禁网 app 命令镜像。
2. 在 no-skill 干净仓库提交 no-skill 提示词。
3. no-skill 运行结束后保存轨迹和 patch，并由独立 verifier 判定 `reward=0`。实时统计轮次，偏好至少 101 轮，但不作为 verifier 门槛。
4. 使用独立 verifier 判分。
5. no-skill `reward=1` 时停止，不运行 with-skill，状态写为 `needs_task_hardening`。
6. no-skill `reward=0` 时，在另一套干净仓库运行 with-skill。with-skill 由独立 verifier 判定；轮次偏好为 70±10，仅用于调优。
7. with-skill `reward=0` 时写入 `needs_skill_revision`。
8. 只有 no-skill `reward=0` 且 with-skill `reward=1` 时写入 `passed`。

API 错误、监控超时、命令超时、Docker 构建失败、`model.patch` 无法应用、patch 无法判分或 verifier 没有生成结构化结果时，状态是 `infrastructure_error`。当前流程不因轮次范围写入 `needs_turn_profile`；这些情况仍不能冒充 verifier 失败或通过。

退出码为：

- `0`：有效对照已通过；
- `20`：题目需要加难；
- `21`：专家 skill 需要返修；
- `22`：基础设施错误。
- `23`：保留作旧版本兼容码；当前流程不因轮次范围退出。

## no-skill 通过后的题目返修

Seed 无 skill 通过，说明当前公开契约不足以构成要求的难度。返修时应从任务自身增加真实推理要求，例如状态组合、操作冲突、失败恢复、兼容性或资源边界。需要同步更新 proposal、参考实现、verifier、难点列表和专家 skill，并重新跑 NOP、Oracle、场景去重和两侧 Agent。

以下做法不能作为有效加难：

- 只增加冷僻固定输入或隐藏常量；
- 缩短时限，依赖随机超时；
- 要求猜测内部文件或私有符号；
- 从 no-skill patch 反推一条专门卡住该实现的断言；
- 保留上一轮工作区或缓存继续运行。

每次返修创建新的 `agent-runs-vN`，保留旧结果。场景目标、核心状态模型、失败恢复或 verifier 行为发生实质变化时，废弃原场景结论，重新执行场景去重和登记。

## with-skill 失败后的 skill 返修

with-skill 失败时不能直接重跑。先读取本轮 `EXPERIMENT_RESULT.json`、`TURN_STATS.json`、`API_RUN.json`、`TRANSCRIPT.jsonl`、`PROGRESS.json`、`VERIFICATION.json` 和 verifier 日志，在本轮运行目录生成 `WITH_SKILL_GAP_ANALYSIS.md`。分析必须逐项写明失败行为、日志证据、Agent 已完成的部分、缺失的状态/关系/验证方法，以及准备补进 skill 的可迁移经验。确认缺口后，才能增加会改变解决策略的专业经验，例如：

- 需要建立的状态、所有权、排序或版本模型；
- 哪些操作会冲突，以及冲突后哪些事实仍有效；
- 如何安排事务边界和失效传播；
- 哪类抽象历史能区分正确设计和常见错误。

不得写入私有测试名、固定失败输入、上一轮断言、参考 patch、内部函数名或逐文件修改步骤。更新后的 skill 仍须为中文，并再次执行语言检查、泄漏复核、题包检查和难点—skill—验证映射。新的 with-skill 专家 skill 必须进入版本化的新提示词；从同一 upstream 干净基线创建新的 with-skill 工作区和 `agent-runs-vN`，绝不复用失败工作区、缓存或 patch。只有完成 `WITH_SKILL_GAP_ANALYSIS.md` 和这些检查，才能启动下一轮。下一轮仍为 `reward=0` 时继续执行同一闭环，不能泛泛重跑；只有连续三次同类基础设施错误或明确的外部凭证/人工停止条件才能暂停。

如果只修改了 `sources/skill/SKILL.md`，可以复用上一轮有真实运行记录且 `reward=0` 的 no-skill 结果：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/prepare_agent_runs.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-name \
  --run-root ./work/YYYY-MM-DD-N-name/agent-runs-v2 \
  --run-seed \
  --env-file ./model.env \
  --accepted-no-skill-result \
    ./work/YYYY-MM-DD-N-name/agent-runs-v1/EXPERIMENT_RESULT.json
```

脚本会核对 upstream、基线 HEAD、proposal、任务契约、no-skill 提示词、verifier 散列、模型 ID、推理强度、轮次上限和 token 上限。任一项变化都拒绝复用。新的 with-skill 仓库仍从 upstream 干净创建。

## 重试和停止条件

每个实验目录只执行一次。不得删除运行结果后在同一目录重试。API 或基础设施错误可以在排除原因后创建新目录重跑；同一错误连续出现三次时停止自动执行并报告，不继续消耗调用额度。

题目返修和 skill 返修没有预设“通过次数”，最终条件是 no-skill `reward=0`、with-skill `reward=1`，以及其他静态和 verifier 检查通过。不能因为尝试次数多而降低标准，也不能为了命中 101/70 的偏好数字让 Agent 空转或选择性删改真实轨迹。

## 自动最终检查、截图和打包

有效对照通过后，监控器自动运行 `finalize_seed_delivery.py`。它先执行：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/capture_final_check.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-name \
  --experiment-result ./work/YYYY-MM-DD-N-name/agent-runs-vN/EXPERIMENT_RESULT.json \
  --output-dir ./work/YYYY-MM-DD-N-name/final-check \
  --benchmark deepSWE
```

`capture_final_check.py` 依次执行中文 skill 检查、proposal validator、题包 checker，并核对 `EXPERIMENT_RESULT.json` 的严格 reward 对照和同目录 `TURN_STATS.json` 的监控统计，保存：

- `FINAL_CHECK.txt`：完整命令和原始输出；
- `FINAL_CHECK.json`：各命令退出码和总结果；
- `FINAL_CHECK.png`：1440 宽仪表盘截图（高度随内容动态），展示四张指标卡、Seed 对照证据与证据散列；F2P/P2P 为从两侧 `verification/VERIFIER_RUN.log` 解析的真实明细，"需要处理"黄色待复核区段仅在存在真实 `[WARN]` 提醒时渲染。

轮次展示遵守真实证据：no-skill 达到最小轮次偏好时才显示 no-skill 轮次，with-skill 落在目标区间时才显示 with-skill 轮次；未命中的真实数值只保留在 `TURN_STATS.json`。不能为了截图修改轨迹。

质检通过后，`finalize_seed_delivery.py` 调用 `build_delivery_zip.py` 构建与题包目录同名的正式 ZIP，并再次对 ZIP 运行 `check_package.py`。最终在 `agent-runs` 中写入 `FINALIZATION_RESULT.json`。截图、质检、散列绑定或 ZIP 复检任一步失败时，监控器返回基础设施错误码 22；PNG 不能手工编辑，也不能代替原始文本和 JSON。已有最终输出时拒绝覆盖。正式交付前还要保留 NOP、Oracle、Docker/verifier 实跑和泄漏扫描证据。

## 飞书上传

用户提供飞书链接后才执行上传，具体操作读取 [feishu-submission.md](feishu-submission.md)。项目飞书配置 `feishu-gsb.toml`（项目根目录或 `--config` 指定路径）是唯一飞书配置，所有读取和写入都使用已验证的用户身份与 `--as user`。

提交只填写目标表中的真实字段：`题目名or编号`、`关联benchmark`、`标注人`、`交付压缩包`、`最终检测skill的检测结果截图`和`状态`。正式 ZIP 与 `FINAL_CHECK.png` 均上传并读回核对后，最后把状态改成`待质检`。同名题目存在时续传原记录，不重复新增。

不得上传 `model.env`、API key、Seed 完整轨迹、私有 verifier 失败详情、参考答案或其他内部材料。链接无权访问、CLI 身份校验失败、目标不唯一、字段不匹配、附件缺失或最终检查未通过时停止上传并报告。
