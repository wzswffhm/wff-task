---
name: obm-task-production
description: 制作和交付 OBM Source benchmark 题包。用户说“生成题包”“生成新的仓库包”“继续生产”“继续返修”“检查最新结果”“准备 no-skill/with-skill”“打包”或“上传”时自动接续当前 OBM 任务；负责场景去重、proposal、中文专家 skill、verifier、手动 Trae 工作区、最终质检和交付。Trae 由用户自行执行，本 skill 不启动或操作 Trae。
---

# OBM题目生产

本 skill 现在采用“用户执行 Trae，Codex 制作和交付”的流程。先判断请求是分析、生产、验证、返修、打包还是上传。分析只读；生产、返修和打包可以写文件。不要把 OBM 与 Harbor、Pair-wise GSB 或其他标注项目混用。

## 自动接续规则

在当前对话已经明确是 OBM 题包生产、返修或验收时，用户只说“继续”“继续生成”“继续返修”“生成新的仓库包”“看最新结果”或“打包”，都视为继续当前题目流程，不要求用户再次写出 skill 名称。先读取当前题号、最近运行版本和已有证据，再决定是继续判分、生成新版本、返修中文专家 skill，还是进入质检。若上下文没有明确的 OBM 任务，单独的“继续”不足以确定操作，不得凭空创建题包。

## Trae 责任边界（硬规则）

- Codex 永远不得启动、接管、激活、切换、关闭或操作 Trae，不得调用 `trae-cn`、`open -a`、AppleScript、原生电脑控制或任何界面自动化。
- Codex 永远不得把提示词发送到 Trae，不得点击输入框、Agent 面板、语言/输入法/语音控件、发送按钮或其他控件。
- Codex 永远不得创建、更新、暂停或删除 Trae heartbeat，也不得调用 `bind`、`monitor` 或 `launch_trae_stage.py`。这些脚本保留在目录中只供历史审计，当前流程禁止使用。
- `prepare_trae_runs.py` 只用于生成干净的 no-skill/with-skill 工作区、`PROMPT.md`、`RUN_RECORD.md` 和 `BASELINE.json`；运行它不启动 Trae。
- 工作区和提示词准备完成后，把路径交给用户。用户自行在 Trae 中运行 no-skill，再根据独立 verifier 结果运行 with-skill。Codex 不代替用户发送或监听。
- 用户完成两侧运行并提供可核验的运行和 verifier 证据后，Codex 才能执行最终质检；质检通过后再打包和上传。

如果任何旧 reference 仍要求 Codex 打开 Trae、发送提示词、创建 heartbeat 或 bind，以本节为准，并停止在这些动作之前。

## 模型运行和验收门槛

- 本 skill 不启动 Trae，也不启动、创建、更新或停止任何定时器、heartbeat 或监听器。用户自行运行对应工作区；Codex 只读取用户提供的磁盘证据。
- no-skill 和 with-skill 必须从相同基线、同一题面和同一 verifier 运行；no-skill 的独立 verifier 必须给出 `reward=0`，with-skill 必须给出 `reward=1`。
- 轮次可以记录用于分析，但不再是验收或打包门槛。无论轮次多少，都不能替代 verifier 结果，也不能把 API、工具或 Docker 异常当作有效失败。
- 运行日志、patch、verifier 输出和基线散列仍需真实可核验；不能手填 reward、伪造运行结果或修改记录制造通过结论。

## 规范和目录

- deepSWE：读取 [references/deepswe.md](references/deepswe.md) 和 [references/common.md](references/common.md)。其他 benchmark 必须先读取对应规范，不能套用 deepSWE 目录或评分规则。
- 新题生产还要读取 [references/scene-dedup.md](references/scene-dedup.md)、[references/task-registry.md](references/task-registry.md) 和 [references/feishu-submission.md](references/feishu-submission.md)。
- 编号使用项目当前日期的 `YYYY-MM-DD-N`，尾号跨日期持续累加。正式目录和 ZIP 使用 `deepSWE_YYYY-MM-DD-N-description`。
- Trae 工作区由准备脚本按题号尾号生成，例如题号 `2026-09-21-1` 对应：

```text
trae-runs-v1/
  1-no-skill/1-no-repo/
  1-with-repo/1-with-repo/
  1-no-skill/PROMPT.md
  1-with-repo/PROMPT.md
  BASELINE.json
```

两侧来自同一 upstream 和同一基线 HEAD。no-skill 提示词只包含题目；with-skill 提示词在同一题目后附加正式包中的中文专家解题思路。专家 skill 是提示词上下文，不安装到 `.trae/skills/`。

## 生产流程

1. 固定 benchmark、仓库、基线提交、需求范围和交付物。deepSWE 先读本地 manifest，选择不同能力类型和不同场景。
2. 建立候选 `scene-profile.json`，同步项目登记表并原子预留编号。按 scene-dedup 规则读取本地题库、项目记录和共享飞书题面库；语义结论必须是“不重复”，否则停止。
3. 写 proposal、公开行为契约、参考实现、verifier、中文专家 skill 和 provenance。正式包的 `sources/skill/SKILL.md` 必须是中文；不能写隐藏测试、参考 patch、私有符号或逐文件答案。
4. 运行 proposal validator、中文检查、包检查、NOP、Oracle、离线 Docker 构建和 verifier。确认 NOP reward=0、Oracle reward=1 后，运行：

```bash
OBM_SKILL_DIR=/Users/xiezhi/Documents/OMB/.codex/skills/obm-task-production
OBM_PYTHON=./.venv/bin/python
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/prepare_trae_runs.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --run-root ./work/YYYY-MM-DD-N-description/trae-runs-v1 \
  --expected-model Doubao-Seed-Evolving
```

5. 只把生成的两个工作区路径和对应 `PROMPT.md` 交给用户。Codex 不打开 Trae、不发送提示词、不创建定时器或监听器。用户手动在 Trae 中打开目标仓库、粘贴对应提示词并执行；完成后运行 `grade_manual_trae.py --mode no-skill`。该流程不要求窗口绑定，也不要求 `TRAE_RUN.json` 或 `MONITOR_REQUEST.json`。
6. no-skill 的独立 verifier 为 `reward=0` 后，用户手动执行 with-skill，再运行 `grade_manual_trae.py --mode with-skill`。Codex 核对两侧 patch、独立 verifier 和 `EXPERIMENT_RESULT.json`；通过后运行最终质检，生成 `FINAL_CHECK.json`、`FINAL_CHECK.txt` 和 `FINAL_CHECK.png`。
7. no-skill verifier 为 `reward=1` 时，返修公开题面、verifier 和中文专家思路，再生成全新版本，重跑两侧。with-skill 未通过时，只补充可迁移的中文专家方法，生成新的 `trae-runs-vN+1` 供用户重跑。不得覆盖旧工作区或修改运行记录来制造达标结果。Codex 不执行 Trae。

## 手动 Trae 判分

`run_trae_experiment.py bind/monitor/grade` 和 `launch_trae_stage.py` 属于旧的窗口绑定流程，当前不要调用。手动运行完成后，使用新增的 `scripts/grade_manual_trae.py`：

```bash
OBM_PYTHON=./.venv/bin/python
OBM_SKILL_DIR=/Users/xiezhi/Documents/OMB/.codex/skills/obm-task-production

"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/grade_manual_trae.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --run-root ./work/YYYY-MM-DD-N-description/trae-runs-v1 \
  --mode no-skill \
  --evidence ./work/YYYY-MM-DD-N-description/trae-runs-v1/1-no-skill/RUN_RECORD.md
```

no-skill 返回 `reward=0` 后，再对 with-skill 工作区运行同一脚本，将 `--mode` 改为 `with-skill`。脚本从仓库基线生成 `model.patch`，调用独立 verifier，并写入 `EXPERIMENT_RESULT.json`。它不读取或创建窗口绑定文件，不启动 Trae，不创建 heartbeat。`RUN_RECORD.md` 只是可选的人类记录；真正的判分依据是生成的 patch、`VERIFICATION.json` 和基线散列。

如果某个旧的手动运行目录已经有本次运行生成的 `trae-output/model.patch` 和 `verification/VERIFICATION.json`，但只有诊断性结果，可以在确认文件确实属于本次运行后加 `--reuse-existing` 重新登记；不要手工伪造 `TRAE_RUN.json` 或 `MONITOR_REQUEST.json`。如果文件来源不确定，创建新的 `trae-runs-vN+1`，不要覆盖旧目录。

## 用户完成 Trae 后的验收

先核对原始运行记录和独立 verifier，再执行最终质检。不能只凭截图、仓库改动或口头说明判定模型结果。检查：

- no-skill 有有效运行记录，独立 verifier `reward=0`；
- with-skill 有有效运行记录，独立 verifier `reward=1`；
- 两侧基线、题目契约、模型和运行版本一致；
- 最终质检生成的 `FINAL_CHECK.json` 中 `ok` 为 `true`，同目录存在未编辑的 `FINAL_CHECK.txt` 和 `FINAL_CHECK.png`；
- proposal、skill、verifier、upstream 哈希与运行记录一致；
- 运行记录没有基础设施错误、跳过测试、隐藏答案或网络违规。

若证据缺失、哈希不一致、with-skill 未通过或最终质检未通过，停止在验收阶段，不打包、不上传。

## 最终质检和打包

用户提供完成证据后，Codex 可以只做本地命令和文件操作：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/capture_final_check.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --experiment-result ./work/YYYY-MM-DD-N-description/trae-runs-vN/EXPERIMENT_RESULT.json \
  --output-dir ./work/YYYY-MM-DD-N-description/final-check \
  --benchmark deepSWE

"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/build_delivery_zip.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --experiment-result ./work/YYYY-MM-DD-N-description/trae-runs-vN/EXPERIMENT_RESULT.json \
  --final-check ./work/YYYY-MM-DD-N-description/final-check/FINAL_CHECK.json \
  --output ./output/deepSWE_YYYY-MM-DD-N-description.zip \
  --benchmark deepSWE
```

打包脚本必须确认状态为 `passed`、no-skill reward=0、with-skill reward=1、最终质检通过和截图存在。对 ZIP 本身再运行 `check_package.py`。ZIP 不得包含 Trae 窗口、提示词、运行记录、验证日志、参考答案、缓存或私有材料。

## 飞书提交

用户要求上传时，遵循 [references/feishu-submission.md](references/feishu-submission.md)：

1. 使用 `/Users/xiezhi/.codex/feishu-gsb.toml`，写入前执行 `lark-cli auth status --json --verify`。
2. 以当前验证用户身份写入题目文件夹名或编号、关联 benchmark、标注人和状态。
3. 上传最终 ZIP 与 `FINAL_CHECK.png`，读回确认两个附件。
4. 附件读回成功后，才把状态改为“待质检”。

飞书写入失败、身份不匹配或附件读回失败时停止，不把状态改成“待质检”。

## 完成标准

- 场景去重结论为“不重复”，项目编号唯一；
- proposal、中文 skill、verifier、provenance 和离线依赖完整；
- NOP reward=0、Oracle reward=1；
- 用户已完成 no-skill/with-skill；no-skill reward=0，with-skill reward=1，均有原始运行证据；
- `FINAL_CHECK.json.ok=true`，并保留 TXT、JSON、PNG；
- 正式 ZIP 通过包检查；
- 飞书两个附件读回无误，状态为“待质检”。

本 skill 的当前流程不会启动 Trae。用户只需在工作区中完成 Trae 对话，完成后把运行结果路径发给 Codex，Codex 负责最终质检、打包和上传。
