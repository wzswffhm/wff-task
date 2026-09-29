# Trae 对照实验（用户执行版）

本文件只规定工作区和证据格式。Trae 的启动、窗口操作、提示词发送、等待和停止都由用户自行完成。Codex 不调用 Trae CLI，不使用界面控制，不创建定时器或 heartbeat。当前手动流程不执行旧的 `bind`、`monitor`、`launch_trae_stage.py` 或旧 `grade`。

## Codex 的职责

1. 在题包通过 proposal、中文 skill、包检查、NOP、Oracle 和离线验证后，运行 `prepare_trae_runs.py`。
2. 把两个精确工作区和各自的 `PROMPT.md` 路径交给用户。
3. 用户完成 no-skill 后，运行 `scripts/grade_manual_trae.py --mode no-skill` 生成 patch 和独立 verifier 结果；只有 reward=0 才继续手动执行 with-skill，再运行该脚本的 `--mode with-skill`。Codex 不替用户打开窗口或发送消息。
4. 用户提供两侧运行日志、独立 verifier 结果和 `EXPERIMENT_RESULT.json` 后，Codex 核验结果，生成最终质检的 JSON、TXT 和 PNG；通过后打包，并按用户要求上传飞书。

手动流程不会生成 `TRAE_RUN.json` 或 `MONITOR_REQUEST.json`。这两个文件只属于历史窗口绑定和 heartbeat 流程，不能为了通过旧脚本而手工补造。`RUN_RECORD.md` 是准备脚本生成的可选记录模板，Trae 不会自动更新它，也不能替代 patch、verifier 和基线散列。

如果旧的手动运行目录已经有本次运行生成的 `trae-output/model.patch` 和 `verification/VERIFICATION.json`，可以给 `grade_manual_trae.py` 加 `--reuse-existing` 将诊断结果升级为当前格式；来源不确定时必须创建新的版本目录，不能覆盖旧证据。

## Seed 运行记录

如果本题使用 Doubao-Seed-Evolving，可以记录运行轮次和结束原因用于分析，但轮次不再是验收门槛。no-skill 必须由独立 verifier 给出 `reward=0`，with-skill 必须给出 `reward=1`。缺少真实运行证据、API 或工具异常时，停止验收。

## 工作区命名

标准题号使用 `YYYY-MM-DD-N`。例如 `2026-09-21-1` 生成：

```text
trae-runs-v1/
  1-no-skill/
    1-no-repo/
    PROMPT.md
    RUN_RECORD.md
  1-with-repo/
    1-with-repo/
    PROMPT.md
    RUN_RECORD.md
  BASELINE.json
```

两个仓库从同一个 upstream 归档独立初始化，基线 HEAD 必须相同。不得把 no-skill 的代码、缓存、测试产物、终端输出或对话结论复制到 with-skill。

## 提示词

- no-skill：只使用对应目录的 `PROMPT.md`。
- with-skill：使用对应目录的 `PROMPT.md`，其中已附加正式包 `sources/skill/SKILL.md` 的专家解题思路。
- 两侧题目契约、upstream、模型、网络和权限保持一致；唯一变量是 with-skill 的专家思路。
- 专家 skill 是提示词上下文，不要安装到 `.trae/skills/`。

## 用户执行顺序

1. 在 no-skill 工作区运行 no-skill 提示词，保留原始运行记录。运行不能以 API、工具或 Docker 错误代替任务结果。
2. 运行独立 verifier。只有 `reward=0` 才继续 with-skill；`reward=1` 说明题目不够难，应返修题目，不能继续。
3. 在 with-skill 工作区运行 with-skill 提示词，并记录实际轮次。
4. with-skill 执行结束后独立 verifier 必须为 `reward=1`。若为 `reward=0`，把失败记录交给 Codex；Codex 补充可迁移的中文专家方法，生成新的 `trae-runs-vN+1` 供用户重跑。
5. 用户需要把实验结果保存在运行目录，至少包含：

```json
{
  "status": "passed",
  "no_skill": {"status": "completed", "reward": 0},
  "with_skill": {"status": "completed", "reward": 1}
}
```

实际结果还必须包含与题包、upstream、verifier、skill 和提示词匹配的哈希或等价证据。没有独立 verifier 结果时，不能只凭 Agent 的最终文字判定通过。

结果文件可以记录以下字段用于分析，但这些字段不参与通过判定：

```json
{
  "no_skill": {"turn_profile": {"turns": 108, "completed": false}},
  "with_skill": {"turn_profile": {"turns": 69, "completed": true}}
}
```

## Codex 交付前检查

Codex 不根据窗口截图推断 Agent 是否完成，只检查磁盘文件：

- no-skill reward=0；
- with-skill reward=1；
- 两侧基线和题目契约相同；
- `FINAL_CHECK.json` 的 `ok=true`；
- `FINAL_CHECK.txt` 和 `FINAL_CHECK.png` 存在且没有被编辑；
- 没有基础设施错误、跳过测试、网络违规或答案泄漏。

证据不完整时停止在验收阶段。不要启动 Trae 补证据，不要创建定时器或监听器，不要执行旧的 `bind`、`monitor` 或 `grade`。

## 返修

- no-skill reward=1：先排除环境故障，再调整题目真实难度，更新 proposal、verifier 和中文 skill，生成新的运行版本，让用户重跑两侧。
- with-skill reward=0：只修改中文专家 skill，不能加入隐藏测试名、固定失败输入、私有符号、参考 patch 或逐文件答案；生成新的运行版本，再交给用户执行。
- 每个新版本必须使用干净工作区，不覆盖旧证据。Codex 不打开新窗口，也不操作旧窗口。

## 完成后的打包和上传

只有 no-skill reward=0、with-skill reward=1、最终质检 `ok=true` 全部成立，Codex 才能运行 `build_delivery_zip.py`、检查 ZIP，并按 `references/feishu-submission.md` 上传 ZIP 和 `FINAL_CHECK.png`。附件读回成功后才把飞书状态改为“待质检”。
