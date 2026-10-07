import pathlib

log = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\memory\2026-10-07.md")
text = """
### D. ★★ 215 探针无效被查出（15:54–15:58，用户「125 进度如何，监控一下」）

- 项目内**无任何 125 编号任务**（harbor-windows=201~217+wsync-142；harbor-weakness=FIN3-WKN-149/150/151；飞书表记录=118）。用户跳过澄清，按最可能指向 `wfflab__wfmt-215`（唯一在跑）继续监控。
- **监控发现致命问题**：QWEN run01 工作区里 agent 自写 `WReparse/NOTES.md` 说明——系统提示要求改 `...\\workspace\\WReparse`（PowerShell 模块）+ `docs/REPARSE-CONTRACT.md`，但容器里是 `wfmt/`（Python 包）；`write_file` 被白名单限制在 `...\\WReparse` 之下（`ERROR: only paths under ... WReparse are writable`）→ **agent 无法就地修 `wfmt/`**，只能把补丁另存到自建目录 → 判分必然 0。
- **根因**：`runner/runner.py` 写死 217 的路径与人设共 7 处（L264/275/361/380/406/411/446/489/513），且 `read_file` 只读 UTF-8（读不了 `assets/sample.wfmt`）、容器内无执行手段。
- **影响面**：217 历史结论**不受影响**（模块名恰好叫 WReparse）；215 controls（no-change×3/golden×3）**有效**（不走 agent 工具，产物 result.json/checks.json 齐全）；215 候选跑分**全部无效**。
- **止血**：`Disable-ScheduledTask oh-wfmt-qwen`（state=Disabled）＋杀 runner python(84016)＋`docker rm -f` 容器；核查 `runs/wfflab__wfmt-215/20261007T141452-…` 无 `result.json` → 不会污染 summarize。
- **产物**：`deliverables/2026-10-07_wfmt215-outside-repair/WFMT_BLOCKER.md`（证据 + 影响面 + 三套方案）。
- **结论**：215 的 QWEN 0 分不是模型能力问题。后续三选一——A 参数化 runner（推荐，所有换名题都要）+补 hex dump；B 换一道"纯源码推理可解"的题；C 改 215 题面（等于新题）。等用户拍板；⛔ 在此之前**不要重启 wfq**。
"""
with log.open("a", encoding="utf-8") as fh:
    fh.write(text)
print("daily log +", len(text))

am = pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\memory\automations"
    r"\fed023f6-1b9c-489c-854d-c3515c9cb0b9\memory.md"
)
am_text = """
## 2026-10-07 15:58 — ★★ 215 QWEN 探针判定「无效」并止血（本轮属结构性阻塞，非模型能力）

**用户指令**：「125 进度如何，监控一下」（项目内无 125 编号任务；按最可能指向 `wfflab__wfmt-215` 继续监控）。

**监控直接命中致命 bug**：QWEN run01 的 agent 自写 `view/environment/workspace/WReparse/NOTES.md` 说明——系统提示要求改 `...\\workspace\\WReparse`（PowerShell 模块），但容器里是 `wfmt/`（Python 包）；`write_file` 白名单**只放行 `...\\WReparse`**（`ERROR: only paths under C:\\task\\environment\\workspace\\WReparse are writable`）→ agent 根本写不进 `wfmt/`，只能把补丁另存 → 判分必然 0 分。

**根因**：`deliverables/2026-10-04_outside-harbor-win/runner/runner.py` 是 **217 专用**，写死 7 处（L264/275/361/380/406/411/446/489/513）；另 `read_file` 只吃 UTF-8（读不了 `assets/sample.wfmt`），容器内无执行手段。

**影响面**：217 结论**不受影响**（模块名恰好 WReparse）；215 controls（no-change×3 / golden×3）**有效**；215 候选跑分（QWEN/OPUS/GLM/KIMI）**全部无效**。

**已止血（15:56–15:58）**：`oh-wfmt-qwen` → **Disabled**；杀 runner python(84016)；`docker rm -f oh-20261007t141452-…`；核查 `runs/wfflab__wfmt-215/20261007T141452-…` **无 `result.json`** → `summarize_model_runs.py` 不会采信。环境已收口（无容器、无 runner 进程）。

**证据**：`deliverables/2026-10-07_wfmt215-outside-repair/WFMT_BLOCKER.md`。

**下次（HOURLY）要点——⛔ 已变更，勿按旧计划走**：
1. **⛔ 绝不要重启 wfq / 不要跑 opus 分片**：215 在修好 harness 前跑什么都无效。
2. 等用户在三个方案里拍板：**A 参数化 runner**（按 `task.toml [policy].mutable_paths` 推导模块目录/契约文档/语言人设 + 补二进制 hex dump；默认值仍解析 WReparse 以保 217 不变）／**B 换一道纯源码推理可解的题**／**C 改 215 题面**（等于新题，controls 与历史分作废）。
3. 若用户选 A：改完 215 的 controls **可以复用**（有效），只需重跑 QWEN×3 → OPUS×3 → GLM/KIMI；epoch 仍用 `2026-10-07T06:12:40+00:00`。
4. 217 线已彻底闭环（桌面交付包 + 飞书 record `reczz28KQU8reW2k`），勿再动。
"""
with am.open("a", encoding="utf-8") as fh:
    fh.write(am_text)
print("automation memory +", len(am_text))
