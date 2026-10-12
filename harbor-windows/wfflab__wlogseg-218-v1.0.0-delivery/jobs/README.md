# jobs/ 归档说明（wfflab__wlogseg-218）

本目录按 `harbor-independent-jobs-archive-v1`（archive-only）重组 218 的 14 轮证据：候选模型 8 轮 + 控制轮 6 轮。

## 与 215/216 的差异（如实声明，不伪造）

| 项 | 215 / 216 | 218（本包） |
|---|---|---|
| 执行引擎 | 本地 Outside-Harbor runner + Windows 容器 | `agent_harness.py`，宿主真实 Windows Runtime（无容器） |
| 判分 | 容器内 tests/test.ps1 | 本机 tests/test.ps1（`judge_runs.py` / `run_218_controls.py` 驱动） |
| `docker_image` / digest | 有 | **无**（字段留 null，`container_note` 说明） |
| `agent/agent.log` | 有 | **未产出**（原始轨迹为 `agent/trajectory.jsonl`） |
| `verifier/raw-runner-result.json` | 有 | **未产出**（原始判分产物为 `verifier/result.json` + `checks.json`） |

每个 trial 的 `result.json → evidence_source` 里写明了真实来源目录与缺项清单，未留存的产物一律不提供、不伪造。

## 分数

- `task__Gh0ADMC`（218-glm-5.3-run1）：0
- `task__lBlN7vk`（218-kimi-k3-run1）：1
- `task__ruPoniZ`（218-opus-5-run1）：0
- `task__SToQv6C`（218-opus-5-run2）：0
- `task__yen3cDM`（218-opus-5-run3）：0
- `task__rGwCJg1`（218-qwen3.8-max-0902-run1）：0
- `task__ZPTIj6v`（218-qwen3.8-max-0902-run2）：0
- `task__LP86F2g`（218-qwen3.8-max-0902-run3）：0
- `task0__9XeiAhR`（218-nop-1）：0
- `task0__W857Ilx`（218-nop-2）：0
- `task0__8Bwpgdp`（218-nop-3）：0
- `task0__dijRIwT`（218-golden-1）：1
- `task0__SIs1Erf`（218-golden-2）：1
- `task0__JN4U05R`（218-golden-3）：1
