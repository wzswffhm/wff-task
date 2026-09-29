# deepSWE_2026-09-28-2-diskcache-atomic-write-batch 交付说明

题号：**2026-09-28-2**（登记表 `work/task-registry.json`，reservation_id `35c1ed43-3429-4984-bbc8-7821dfb5c3f2`）
正式包：`output/deepSWE_2026-09-28-2-diskcache-atomic-write-batch`
上游：grantjenks/python-diskcache @ `323787f507a6456c56cce213156a78b17073fe00`（v5.6.3，Apache-2.0）
关联官方题：`sqlite-utils-safe-import-checkpoints`（核心能力：批量写入的原子提交/回滚与持久化恢复）

---

## ⚠️ 当前状态：暂停（去重结论为 high-risk，不得继续打包）

补做共享飞书题面库复核后发现：本项目已在 python-diskcache 上产出 7 道以上题目，且 2026-09-24-4 已覆盖"批次原子可见 + 未决批次 + committed/stable 读取"这一核心机制族。共享表该行已改为`疑似重复`并读回确认（record_id `recvwtXeIufJIW`）。

按规范 high-risk 不得继续生产。**请先在下面两个方向中选一个**：

- **A. 换上游仓库**（推荐）：复用已完成的 verifier 形态与流程，换一个未被本项目使用过的纯 Python 库，重新选题、重新占位、重跑 NOP/Oracle。
- **B. 重构场景后继续**：把场景改到脱离"批量变更原子可见"机制族的方向（例如磁盘配额与淘汰策略的跨分片一致性、或索引与文件系统的校验与自愈），需重新建档、重新复核、重新占位。

题包资产、参考实现、NOP/Oracle 证据都保留在原地，换仓库时可复用脚手架，但 proposal、skill、verifier 需按新场景重写。

## 一、已完成并通过的环节

| 环节 | 命令 / 证据 | 结果 |
|---|---|---|
| 场景去重 | `check_scene_overlap.py --benchmark-root Benchmark/deep-swe-prompts/tasks`（113 道官方题面）+ 人工语义比较与改名测试 | 最高召回 0.1422；结论 `distinct`，见 `scene-overlap-review.md` |
| 编号预留 | `task_registry.py reserve`（经 `work/win_task_registry.py` 兼容垫片） | `2026-09-28-2`，状态已置 `candidate` |
| 交付格式校验 | 生产侧 `proposal_validator/validate_proposals.py` + 质检侧 `scripts/validate_proposals.py` | 均通过 |
| 专家 skill 中文检查 | `scripts/check_skill_language.py` | PASS（汉字 1264 / 英文字母 0） |
| **NOP 实跑** | `work/.../runs/nop-*/reward.json` | **reward=0**（F2P 0/13 失败：`'Cache' object has no attribute 'batch'`；P2P 31/31 通过） |
| **Oracle 实跑** | `work/.../runs/oracle-*/reward.json` | **reward=1**（F2P 13/13、P2P 31/31 全通过） |
| 包静态检查 | `scripts/check_package.py --benchmark deepSWE` | 只剩 Windows 无法设置的可执行位告警（容器内已用 `chmod +x` + `python grader.py` 规避） |
| Trae 工作区 | `prepare_trae_runs.py --expected-model Doubao-Seed-Evolving` | `work/.../trae-runs-v1/2-no-skill`、`2-with-repo`、`BASELINE.json` |

NOP/Oracle 在本机隔离 venv 中真实执行，与容器内同一套 `grader.py` 逻辑，只是没有 Docker 层。

## 二、还差什么（必须由人完成）

### 1. 飞书共享题面库（前置门槛，未完成）

`lark-cli` 的用户身份 refresh token 已过期，`--as user` 写入无法进行。规范明确：读回值为`不重复`之前不允许创建正式包与 Trae 工作空间。目前已生成授权二维码，授权后我会写入并读回六项字段：`题目编号`、`题面`、`核心场景`、`对比题面`、`去重判断`=`不重复`、`判断依据`。

### 2. Trae no-skill / with-skill 双跑（我不得启动或操作 Trae）

请在 Trae 中分别打开：

- `work/2026-09-28-2-diskcache-atomic-write-batch/trae-runs-v1/2-no-skill/2-no-repo`
- `work/2026-09-28-2-diskcache-atomic-write-batch/trae-runs-v1/2-with-repo/2-with-repo`

分别粘贴同目录下的 `PROMPT.md`，模型固定 `Doubao-Seed-Evolving`，完成后提交。然后执行：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/grade_manual_trae.py" \
  --task-dir ./output/deepSWE_2026-09-28-2-diskcache-atomic-write-batch \
  --run-root ./work/2026-09-28-2-diskcache-atomic-write-batch/trae-runs-v1 \
  --mode no-skill
# no-skill 的独立 verifier 必须 reward=0
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/grade_manual_trae.py" ... --mode with-skill
# with-skill 必须 reward=1
```

### 3. 最终质检与打包

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/capture_final_check.py" \
  --task-dir ./output/deepSWE_2026-09-28-2-diskcache-atomic-write-batch \
  --experiment-result ./work/2026-09-28-2-diskcache-atomic-write-batch/trae-runs-v1/EXPERIMENT_RESULT.json \
  --output-dir ./work/2026-09-28-2-diskcache-atomic-write-batch/final-check \
  --benchmark deepSWE

"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/build_delivery_zip.py" \
  --task-dir ./output/deepSWE_2026-09-28-2-diskcache-atomic-write-batch \
  --experiment-result ./work/2026-09-28-2-diskcache-atomic-write-batch/trae-runs-v1/EXPERIMENT_RESULT.json \
  --final-check ./work/2026-09-28-2-diskcache-atomic-write-batch/final-check/FINAL_CHECK.json \
  --output ./output/deepSWE_2026-09-28-2-diskcache-atomic-write-batch.zip \
  --benchmark deepSWE
```

打包后再对 ZIP 跑一次 `check_package.py`，并把登记表状态改为 `packaged`。

## 三、已知限制（如实记录）

- **Docker 不可用**：本机没有 docker 命令，`--network=none` 的镜像构建与容器内判分未实跑；NOP/Oracle 证据来自本机 Python 3.13 隔离环境的等价执行。正式验收应在 Linux + Docker 环境重跑 `verify_agent_patch.py`。
- **Windows 平台差异**：`task_registry.py` 依赖 `fcntl`（通过 `work/win_task_registry.py` 垫片运行，无跨进程互斥，仅单窗口有效）；文件系统无可执行位，`check_package.py` 对目录模式报 `test.sh`/`grader.py` 不可执行（ZIP 打包时可写入 0o755 属性）。
- **本地题库**：官方 113 道题面已拉取到 `Benchmark/deep-swe-prompts/tasks`（只保留 instruction.md 与 manifest.json）；`Benchmark/deep-swe-main` 里残留了官方 solution/tests 副本，删除被系统安全机制拦截，**未被读取、也不在任何交付物内**，建议手动清掉该目录。
