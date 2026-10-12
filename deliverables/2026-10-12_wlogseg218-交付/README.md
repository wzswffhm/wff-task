# wfflab__wlogseg-218 · 交付记录（2026-10-12）

## 1. 交付物

| 项 | 值 |
|---|---|
| ZIP | `package/wfflab__wlogseg-218-v1.0.0-delivery.zip` |
| 大小 | 54,872,624 B（raw 53.4 MiB / 232 entries） |
| sha256 | `9a3970d8e76dc1864e747eb20f3e4a0871d7895ddc68b756df27923d9aee5e4c` |
| 顶层 | 单一同名目录 `wfflab__wlogseg-218-v1.0.0-delivery/` |
| 二层 | `instruction.md` `task.toml` `environment/` `jobs/` `solution/` `tests/` `verifier/`（与 215/216 **同构**） |
| 自检 | `verify_218_delivery.py` → **PASS**（sha256、顶层/二层、关键件、14 个 trial、禁入项全过） |

> 打包脚本：`harbor-windows/_qc_runs/wlogseg-build/build_218_delivery.py`（stage + zip + sha256）。

## 2. 分数与门禁（14 轮，全部 VALID）

| 轮次 | 载荷 | 分数 | 逐项 |
|---|---|---|---|
| golden ×3 | `solution/solve.ps1` 注入参考解 | **1 / 1 / 1** | 25/25 |
| no-change ×3 | 交付初始态直接判分 | **0 / 0 / 0** | 8/25 |
| Qwen3.8-Max-0902 ×3 | 候选 | 0 / 0 / 0 | 8、20、5 /25 |
| **Opus 5 ×3（4router.net）** | 候选 | 0 / 0 / 0 | 23、24、23 /25 |
| GLM-5.3 ×1 | 候选 | 0 | 23/25 |
| Kimi K3 ×1 | 候选 | **1** | 25/25 |

**区分度准入（条件 2）**：Qwen 与 Opus 的 `model_score_sum` 都是 0，则比逐项通过数 ——
**Opus 70 > Qwen 33**，准入 **PASS**。无 INVALID 轮次。

Opus 三轮共同失分点是同一批 F2P 难点（`f2p-truncated-segment-body-reports-truncated`
3/3、`f2p-index-entry-mismatch-reports-structure` 2/3）；Kimi 同题 25/25、Golden=1，
说明该难点可解，非题面/测试缺陷。

## 3. 与 215 / 216 的差异（如实声明）

| 项 | 215 / 216 | 218（本包） |
|---|---|---|
| 执行引擎 | 本地 Outside-Harbor runner + Windows 容器 | `agent_harness.py`，**宿主真实 Windows Runtime**（无容器） |
| 判分 | 容器内 `tests/test.ps1` | 本机 `tests/test.ps1`（`judge_runs.py` / `run_218_controls.py` 驱动） |
| `docker_image` / digest | 有 | 无（字段 null + `container_note`） |
| `agent/agent.log` | 有 | 未产出（原始轨迹为 `agent/trajectory.jsonl`） |
| `verifier/raw-runner-result.json` | 有 | 未产出（原始判分为 `verifier/result.json` + `checks.json`） |

每个 trial 的 `result.json → evidence_source` 写明真实来源目录与缺项清单；
**未留存的产物一律不提供、不伪造**。`jobs/README.md` 有同一份声明。

## 4. 飞书回写

| 项 | 值 |
|---|---|
| Base / 表 | `EsJebL8JJaf7g4sIbItcnMFgnvg` / `tblRDxcGkblflMBA` |
| 记录 | `reczz28MRVnWkD2v`（**新建**，表内原无 218 行） |
| `文本` | `wfflab__wlogseg-218-v1.0.0-delivery.zip` |
| `标注员` | `wff`（`ou_f4e4bc01ed9be1ef4cbaedcdf8f19d45`） |
| `甲方ID` | `wfflab__wlogseg-218-v1.0.0-delivery.zip` |
| `题目方向` | `Windows/文件格式与序列化（分段追加日志容器：8 字节索引条目 + 8 字节段对齐 + 标准 CRC-32 + truncated/structure 错误分类）/Python/缺陷修复` |
| `提示词` | 题包 `instruction.md` 原文（2,437 字符） |
| `作业压缩包` | `wfflab__wlogseg-218-v1.0.0-delivery.zip`(54,872,624) |
| `分数截图` | `score_summary.png`(83,170) |
| `oracle/nop截图` | `oracle_nop_controls.png`(115,122) |
| `状态` | **未写入、未改动**：新建与两次写入前后读回均为 `待提交`（飞书新建行默认值），`status_untouched=true` |

回执：`evidence/upload-218.json`（含每个附件的 field_id / 名称 / 字节数 / 读回校验）。
执行脚本：`submit_218.py`（新建行 + 三附件，不写状态）、`fill_218_text_fields.py`（三个文本字段，不写状态）。

## 5. 本地证据索引

| 路径 | 内容 |
|---|---|
| `package/…-delivery.zip` + `.sha256` | 交付包与校验和 |
| `build/…-delivery/` | 打包前的 stage 树（可逐文件比对） |
| `evidence/images/score_summary.png` | 模型得分与区分度判据（截图） |
| `evidence/images/oracle_nop_controls.png` | golden / no-change 六轮对照（截图） |
| `evidence/upload-218.json` | 飞书写回回执 |
| `harbor-windows/wfflab__wlogseg-218-v1.0.0-delivery/jobs/` | 14 轮归档（config/result/lock/job.log/README + 每轮 agent/verifier） |
| `harbor-windows/_qc_runs/wlogseg-build/controls-218/` | 六轮控制轮的原始判分产物 |
| `harbor-windows/_qc_runs/wlogseg-build/evidence/` | 区分度报告与 4router 端点处置说明 |

## 6. 复现命令

```powershell
$py = 'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe'
$S  = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wlogseg-build'
& $py $S\run_218_controls.py        # golden x3 / no-change x3
& $py $S\assemble_218_jobs_archive.py   # 组装 jobs/（14 轮，archive-only）
& $py $S\build_218_delivery.py      # stage + 打 zip + sha256
& $py $S\make_218_screenshots.py    # 两张证据截图
& $py $S\verify_218_delivery.py     # 交付包自检
& $py $S\submit_218.py --confirm-write  # 飞书写回（新建行 + 三附件，不写状态）
```

## 7. 尚未执行

- Docker 内构建与真实 Windows Harbor 容器的动态门禁；
- `harbor-windows/_index` 登记（本地索引/校验和汇总）；
- git 提交（按约定只在用户明确要求时执行）。
