# wfflab__wlogseg-218 · 交付记录（2026-10-12，按新版甲方自检整改）

## 1. 交付物

| 项 | 值 |
|---|---|
| ZIP | `package/wfflab__wlogseg-218-v1.0.0-delivery.zip` |
| 大小 | 54,918,649 B |
| sha256 | `bdbadc3397f798d8dc3f942ac60f885502be3b81453899ef08d922db9f298bf4` |
| 顶层 / 二层 | 单一同名目录；`instruction.md` `task.toml` `environment/` `jobs/` `solution/` `tests/` `verifier/` |
| 任务身份 | `wfflab__wlogseg-218` v1.0.0；`harbor_task_checksum = 4b02351d40bb4ffcd9d55260506ea3e2b11e2b72b5e988b4bbbf9bc125746b8d` |

> 注：`extras/`（伴随材料）**不进交付包**，与 215/216 形态一致；它已移出题包到
> `harbor-windows/_qc_runs/wlogseg-build/extras-218/`。这一点对本轮很关键 ——
> Harbor 的 checksum 会把 `extras/` 算进去，交付包却不含它，两边就对不上（见 §3）。

## 2. 14 轮真实容器跑分（Harbor + Windows containers）

| 轮次 | 正式分 | 逐项通过 | F2P | P2P | 耗时 |
|---|---|---|---|---|---|
| qwen ×3 | 0 / 0 / 0 | 62/75 | — | — | 240 / 291 / 279 s |
| opus ×3 | 0 / 0 / 0 | **69/75** | — | — | 573 / 948 / 664 s |
| glm ×1 | 0 | 24/25 | — | — | 1241 s |
| kimi ×1 | 0 | 8/25 | — | — | 461 s |
| oracle ×3 | **1 / 1 / 1** | 25/25 | 全过 | 全过 | ~20 s |
| no-change ×3 | **0 / 0 / 0** | 8/25 | 至少 1 项 FAIL | 全过 | ~20 s |

**区分度准入（条件 2）**：Qwen 与 Opus 的 `model_score_sum` 都是 0 → 比逐项，
**Opus 69 > Qwen 62** → PASS。

14 轮全部为 Harbor 原生 job（`jobs/<trial>/` 含 config/lock/result/trial.log、
`agent/`、`artifacts/manifest.json`、`verifier/`），且 `task_checksum` 全部等于
`4b02351d…`。

## 3. 本轮针对 2026-10-12 版自检包的整改

| # | 原问题 | 处理 |
|---|---|---|
| 1 | `environment/adapter.toml`：`Cannot overwrite a value (at line 38)` —— 顶层扁平键与同名 `[table]` 段重名 | 9 个表段收进 `local_runner` 命名空间，扁平键保留（`runner.py` 本就不读此文件，行为不变） |
| 2 | `referenced files are missing: solution\reference\wlogseg, tests\test_wlogseg_semantics.py` | 参考解落 `solution/reference/wlogseg`；语义测试落 `tests/test_wlogseg_semantics.py`，并补 `tests/verifier/` |
| 3 | 容器内 Oracle 恒 0 分（真因：workspace 只在镜像的 `C:\testbed`，而 `solve.ps1`/`test.ps1` 推导成 `C:\environment\workspace`；Harbor 调这两个入口**不传参数**） | 两个入口改为按 `env → environment\workspace → C:\testbed → cwd` 择优解析 |
| 4 | jobs「was run against a different Task checksum」 | Harbor 的 `dirhash` **含 `jobs/`**，自检期望值**排除 `jobs/`**；且跑分时题包还含 `extras/`。→ 把 `extras/` 移出、跑分期间题包内不放 `jobs/`，重跑 14 轮后 checksum 与期望值逐字一致 |
| 5 | 双引号在容器命令链上被吞（`dir /s /b "C:\testbed"` 必失败） | 自研 Harbor agent 的所有命令改走「写临时 `.cmd` → 执行 → 删除」通道 |

## 4. 新版自检结论（2026-10-12 版 windows-harbor-qc）

```
结论：BLOCKED
- 交付目录：        PASS
- 四模型门禁：      PASS
- 四模型原始 jobs： PASS
- Oracle/NOP：      PASS
- 十项人工质量复核： BLOCKED   ← 首次运行的预期状态，需填 quality-review.json
```

报告与原始产物：`evidence/qc-new-version/`（`report.md`、`report.json`、
`model-gate.json`、`model-jobs.json`、`harbor/` 下 6 轮 Oracle/NOP 的 CLI 日志与 job）。

> 按甲方 SKILL：十项人工硬门禁需由质检方按采购手册（WIP 94 项 + D01–D20）逐项
> 提供证据；缺任一项时自动门禁即使全过，最终结论也只能是 `BLOCKED`。
> 模板已生成在 `evidence/qc-new-version/quality-review-template.json`。

## 5. 飞书回写状态（**待人工放开写权限**）

| 项 | 值 |
|---|---|
| Base / 表 | `EsJebL8JJaf7g4sIbItcnMFgnvg` / `tblRDxcGkblflMBA` |
| 记录 | `reczz28MRVnWkD2v`（本轮交付前创建） |
| 标注员 | `wff` |
| 当前状态 | **待质检**（已流转） |
| 当前附件 | **旧版**：zip(54,872,624)、score_summary.png(83,170)、oracle_nop_controls.png(115,122) |
| 待替换为 | zip(54,918,649)、score_summary.png(83,622)、oracle_nop_controls.png(126,388) |

**阻塞**：该行状态已是「待质检」，标注员此时**没有写权限** —— 替换附件被飞书拒绝
（`permission_denied` / code `800020812`）。这与 `references/10-windows-ops-pitfalls.md` §6
记录的坑一致：状态流转到「待质检」后写权限立即收回。

处理办法（二选一，均需人在飞书界面操作）：
1. 把该行状态改回 **待提交 / 待返修**，我随即用 `submit_218.py --confirm-write`
   完成「先删旧、再传新」并读回校验；
2. 或由有权限的账号直接替换三个附件字段。

状态字段本身我方**未做任何改动**（首次上传前后读回均为 `待提交`，本轮读取为 `待质检`）。

## 6. 本地证据索引

| 路径 | 内容 |
|---|---|
| `package/…zip` + `.sha256` | 交付包与校验和 |
| `build/…-delivery/` | 打包前 stage 树 |
| `evidence/images/` | 两张交付截图（模型得分与区分度 / Oracle-NOP 对照） |
| `evidence/qc-new-version/` | 2026-10-12 版自检报告与原始产物 |
| `evidence/upload-218.json` | 首次上传回执（旧版附件） |
| `harbor-windows/wfflab__wlogseg-218-v1.0.0-delivery/jobs/` | 14 个原生 Harbor job |
| `harbor-windows/_qc_runs/wlogseg-build/model-rounds/` | 8 轮模型原始产物与日志 |
| `harbor-windows/_qc_runs/wlogseg-build/container-controls2/` | 6 轮控制原始产物与日志 |
| `harbor-windows/_qc_runs/wlogseg-build/harbor_agent/` | 自研 Harbor agent（宿主侧循环 + 容器内工具） |

## 7. 复现命令

```powershell
$py = 'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe'
$S  = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wlogseg-build'
& $py $S\run_218_model_rounds.py --max-steps 40      # 8 轮模型（容器）
# 6 轮控制：harbor run --agent oracle|nop（见 container-controls2/rerun.log）
& $py $S\assemble_218_harbor_jobs.py                  # 组装 jobs/（14 轮）
& $py $S\build_218_delivery.py                        # 打 zip + sha256
& $py $S\make_218_screenshots.py                      # 两张截图
& $py $S\run_218_full_qc.py                           # 新版自检（含真实 Oracle/NOP）
& $py $S\submit_218.py --confirm-write                # 飞书写回（需行处于可写状态）
```

## 8. 尚未完成

- **飞书附件替换**（被状态/权限阻塞，见 §5）
- 十项人工质量复核的 `quality-review.json`（质检方职责）
