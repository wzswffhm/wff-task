# wfflab__wchunk-216 交付包（jobs 目录按甲方参考格式重组）

- 生成时间：2026-10-10T20:33:48+08:00
- 题包身份：`task_hash_platform=72ea01be25b665bfe548f71e0f57599a44fc86aaa19475227471667f910a0afb`
（跑分口径 `task_hash_runner=75f37034e86c6d352d906a2209264c051f3adc623392f9cf4cdbd363902cb354`）
- 归档产物：`wfflab__wchunk-216/`（305 个文件）+ `wfflab__wchunk-216-jobs-archive-v1.1.0.zip`（883,209 B）
- zip sha256：`72a46039443a77184d54080af1cd7130193c8ad9ac47fd7091bb93fe6e61624b`（另见同名 `.sha256`）

## 1. 这次做了什么

1. **补跑 GLM 轮**：本地 Outside-Harbor runner 于 2026-10-10 20:02–20:12 重跑 GLM，verdict = 0、`run_validity=VALID`、turns=12，并带 `task_identity.json`（task_hash=`75f37034…`、image_digest=`sha256:8bb261b4fc92…`）。
2. **按参考包 `harbor-record-42-direct-jobs` 的 jobs 目录格式重组交付包**：`jobs/{config,result,lock}.json + job.log + 14 个 trial 目录`，控制轮为 Harbor CLI 原生 trial（原样），模型轮为 runner 原始产物（逐字节保留）。
3. **校验**：`verify_216_jobs_archive.py` 384 项检查全部通过（结构完整、reward 自洽、控制轮逐字节等于原生、模型轮逐字节等于 runs、lock.source_mapping 覆盖全部文件且 hash 正确）。

## 2. 归档内容（14 轮）

| trial | 角色 | 模型 | 引擎 | run_id | reward | 完成时间 | 跑分时 task_hash |
|---|---|---|---|---|---|---|---|
| `wfflab__wchunk-216__glm-5.3-01-ff7f` | 候选 | glm-5.3 | Outside-Harbor runner | 20261010T200244-candidate-glm-5.3-01-ff7f | 0.0 | 2026-10-10 20:12 | 有 |
| `wfflab__wchunk-216__kimi-k3-01-664d` | 候选 | kimi-k3 | Outside-Harbor runner | 20261010T005740-candidate-kimi-k3-01-664d | 0.0 | 2026-10-10 01:36 | 无 |
| `wfflab__wchunk-216__opus-5-01-6142` | 候选 | opus-5 | Outside-Harbor runner | 20261009T234344-candidate-opus-5-01-6142 | 1.0 | 2026-10-10 00:01 | 无 |
| `wfflab__wchunk-216__opus-5-02-6713` | 候选 | opus-5 | Outside-Harbor runner | 20261010T000129-candidate-opus-5-02-6713 | 0.0 | 2026-10-10 00:11 | 无 |
| `wfflab__wchunk-216__opus-5-03-ec7e` | 候选 | opus-5 | Outside-Harbor runner | 20261010T001134-candidate-opus-5-03-ec7e | 1.0 | 2026-10-10 00:21 | 无 |
| `wfflab__wchunk-216__qwen3.8-max-0902-01-8cea` | 候选 | qwen3.8-max-0902 | Outside-Harbor runner | 20261009T223252-candidate-qwen3.8-max-0902-01-8cea | 0.0 | 2026-10-09 22:58 | 无 |
| `wfflab__wchunk-216__qwen3.8-max-0902-02-16f0` | 候选 | qwen3.8-max-0902 | Outside-Harbor runner | 20261009T225811-candidate-qwen3.8-max-0902-02-16f0 | 0.0 | 2026-10-09 23:29 | 无 |
| `wfflab__wchunk-216__qwen3.8-max-0902-03-ffcc` | 候选 | qwen3.8-max-0902 | Outside-Harbor runner | 20261009T232924-candidate-qwen3.8-max-0902-03-ffcc | 0.0 | 2026-10-09 23:43 | 无 |
| `wfflab__wchunk-216__DCNJZry` | 控制 | oracle | Harbor CLI | - | 1 | 2026-10-10 01:44 | harbor-lock |
| `wfflab__wchunk-216__kyMGGir` | 控制 | oracle | Harbor CLI | - | 1 | 2026-10-10 01:45 | harbor-lock |
| `wfflab__wchunk-216__ZhtzFma` | 控制 | oracle | Harbor CLI | - | 1 | 2026-10-10 01:45 | harbor-lock |
| `wfflab__wchunk-216__oRFXfq6` | 控制 | nop | Harbor CLI | - | 0 | 2026-10-10 01:45 | harbor-lock |
| `wfflab__wchunk-216__d46javP` | 控制 | nop | Harbor CLI | - | 0 | 2026-10-10 01:46 | harbor-lock |
| `wfflab__wchunk-216__96aas5L` | 控制 | nop | Harbor CLI | - | 0 | 2026-10-10 01:46 | harbor-lock |

汇总：oracle×3 = 1 / nop×3 = 0；glm-5.3 = [0.0]；kimi-k3 = [0.0]；opus-5 = [1.0, 0.0, 1.0]；qwen3.8-max-0902 = [0.0, 0.0, 0.0]。

## 3. 与参考包的目录对应

| 参考包 | 本包 |
|---|---|
| `jobs/config.json` / `result.json` / `lock.json` / `job.log` | 同名字段一致（本包为超集，另有说明性字段） |
| `jobs/<trial>/{config,lock,result}.json + trial.log` | 同构 |
| `jobs/<trial>/agent/` + `verifier/` + `artifacts/original-job/` | 同构（模型轮另带原始 agent.log/prompt/task_identity 等） |
| 控制轮 agent/verifier 文件 | 参考包有的文件本包都有；本包另带 QC 原生的 report.json/reward.json/reward-details.json |

## 4. 需要你知道的两点（未做任何修饰）

1. **7 轮缺跑分时 task_hash**：`kimi-k3-01`、`opus-5-01/02/03`、`qwen3.8-max-0902-01/02/03` 这 7 轮执行于 2026-10-09 22:32 – 2026-10-10 01:36，当时 runner 还没有写 `task_identity.json`/`prompt.*.txt`（该能力 2026-10-10 17:56 才提交）。它们有完整原始 `agent.log`/`test.log`/`checks.json`/`result.json`，但没有跑分那一刻的 task_hash 快照；`jobs/ARCHIVE-NOTES.md` 已逐条声明。
2. **模型轮不是 Harbor CLI 直跑**：本机没有甲方的 `model_bridge:ModelBridge`/`evidence_env:EvidenceEnvironment` 插件，模型轮由本地 runner 执行，因此 `config.json` 的 agent 名是 `runner:LocalModelRunner`，`artifacts/original-job/` 是 runner 侧等价记录。

## 5. 复现

```powershell
$py = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
& $py -X utf8 _qc_runs\tools\assemble_216_jobs_archive.py --zip
& $py -X utf8 _qc_runs\tools\verify_216_jobs_archive.py
& $py -X utf8 _qc_runs\tools\compare_archive_shapes.py
```

原始交付包（本次归档的上游）：`wfflab__wchunk-216-v1.1.0-delivery.zip` sha256`d215e87f8039d0e7d4387400177f22f198c0b28bbfa65f56e23f45a9278e73f1`
