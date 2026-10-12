# wfflab__wchunk-216 jobs 归档说明（harbor-independent-jobs-archive-v1）

本目录按甲方参考包 `harbor-record-42-direct-jobs` 的 jobs 目录格式重组，**archive-only**：没有新增任何执行、run id、score、response 或 task checksum。

## 1. 结构与参考包的对应

| 参考包 | 本包 |
|---|---|
| `jobs/config.json`（schema/archive_only/task_id/n_trials/trials） | 同名字段一致 |
| `jobs/result.json`（n_total_trials + trials[].original_result） | 同名字段一致 |
| `jobs/lock.json`（source_mapping 全量 sha256） | 同名字段一致（本包另记 task_hash_platform / task_hash_runner） |
| `jobs/job.log`（`===== Original job: <name> =====` 分段） | 同格式 |
| `jobs/<trial_name>/{config,lock,result}.json + trial.log + agent/ + verifier/ + artifacts/original-job/` | 同构 |

## 2. 证据来源（逐轮）

| trial | 角色 | 引擎 | run_id | verdict | 跑分时间 | 跑分时 task_hash |
|---|---|---|---|---|---|---|
| `wfflab__wchunk-216__glm-5.3-01-ff7f` | candidate-GLM | outside-harbor-runner | 20261010T200244-candidate-glm-5.3-01-ff7f | 0 | 2026-10-10 20:12:09 | 有（跑分时 task_hash） |
| `wfflab__wchunk-216__kimi-k3-01-664d` | candidate-KIMI | outside-harbor-runner | 20261010T005740-candidate-kimi-k3-01-664d | 0 | 2026-10-10 01:36:20 | 无 |
| `wfflab__wchunk-216__opus-5-01-6142` | candidate-OPUS | outside-harbor-runner | 20261009T234344-candidate-opus-5-01-6142 | 1 | 2026-10-10 00:01:29 | 无 |
| `wfflab__wchunk-216__opus-5-02-6713` | candidate-OPUS | outside-harbor-runner | 20261010T000129-candidate-opus-5-02-6713 | 0 | 2026-10-10 00:11:34 | 无 |
| `wfflab__wchunk-216__opus-5-03-ec7e` | candidate-OPUS | outside-harbor-runner | 20261010T001134-candidate-opus-5-03-ec7e | 1 | 2026-10-10 00:21:09 | 无 |
| `wfflab__wchunk-216__qwen3.8-max-0902-01-8cea` | candidate-QWEN | outside-harbor-runner | 20261009T223252-candidate-qwen3.8-max-0902-01-8cea | 0 | 2026-10-09 22:58:11 | 无 |
| `wfflab__wchunk-216__qwen3.8-max-0902-02-16f0` | candidate-QWEN | outside-harbor-runner | 20261009T225811-candidate-qwen3.8-max-0902-02-16f0 | 0 | 2026-10-09 23:29:24 | 无 |
| `wfflab__wchunk-216__qwen3.8-max-0902-03-ffcc` | candidate-QWEN | outside-harbor-runner | 20261009T232924-candidate-qwen3.8-max-0902-03-ffcc | 0 | 2026-10-09 23:43:43 | 无 |
| `wfflab__wchunk-216__DCNJZry` | oracle | harbor-cli | - | 1 | 2026-10-10 01:44:49 | 有（harbor lock digest） |
| `wfflab__wchunk-216__kyMGGir` | oracle | harbor-cli | - | 1 | 2026-10-10 01:45:11 | 有（harbor lock digest） |
| `wfflab__wchunk-216__ZhtzFma` | oracle | harbor-cli | - | 1 | 2026-10-10 01:45:38 | 有（harbor lock digest） |
| `wfflab__wchunk-216__oRFXfq6` | nop | harbor-cli | - | 0 | 2026-10-10 01:45:59 | 有（harbor lock digest） |
| `wfflab__wchunk-216__d46javP` | nop | harbor-cli | - | 0 | 2026-10-10 01:46:25 | 有（harbor lock digest） |
| `wfflab__wchunk-216__96aas5L` | nop | harbor-cli | - | 0 | 2026-10-10 01:46:42 | 有（harbor lock digest） |

## 3. 已知差异 / 缺项（如实声明，未做任何修饰）

- 控制轮（oracle×3 / nop×3，共 6 轮）是 **Harbor CLI 直跑**的原生 trial 目录，文件原样迁移，未改动任何字段。
- 候选模型轮（8 轮）由 **本地 Outside-Harbor runner** 执行（`deliverables/2026-10-04_outside-harbor-win/runner/runner.py`），不是 Harbor CLI 原生 job：因此 `config.json` 的 agent 名为 `runner:LocalModelRunner`，`artifacts/original-job/` 内是 runner 侧的 job 级等价记录（不是 Harbor 的 lock/job.log）。
- 模型轮的 `agent/trajectory.jsonl` 由该轮原始 `agent/agent.log` 结构化导出（逐条保留原文，未经改写）；`agent/agent.log` 同时原样保留。
- 模型轮 `verifier/result.json` 是按参考包 `outside-harbor-result-v1` 口径对原始 `verifier/raw-runner-result.json`（runner 原始 aggregate-v1 报告）的字段投影，`derived_from` 已标注；`items` 的每一项都直接取自原始 cases。
- **跑分时 task 身份绑定**：只有 GLM 轮（2026-10-10 20:02 重跑）带 `agent/task_identity.json`（task_hash / image_digest）与 `prompt.system.txt`/`prompt.task.txt`；其余 7 轮执行时 runner 尚未写这些文件，只有 `task_version=1.1.0` 与原始 `test.log`/`checks.json`，没有跑分时的 hash 快照。
- 题包身份（当前交付树）：`task_hash_platform=72ea01be25b665bfe548f71e0f57599a44fc86aaa19475227471667f910a0afb`，`task_hash_runner=75f37034e86c6d352d906a2209264c051f3adc623392f9cf4cdbd363902cb354`。
