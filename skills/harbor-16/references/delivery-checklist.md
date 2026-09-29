# 交付前自检（harbor-skill）

对 staging 目录或最终 zip 逐项打勾。任一 P0 未勾 = 禁止提交。

对照质检挂单 `zq2026080704332`：缺 baseline/oracle / 空壳 quality → 直接不通过（**smoke 现行可不跑**）。

## P0（质检硬伤）

- [ ] **本地**已跑通 baseline/nop（`reward=0`）、oracle（`reward=1` 且 quality 已执行）；**smoke 可选，不跑不阻断**
- [ ] 已做 **全量本地备份**到 `task/_full_job_backups/<作业ID>/...`（含全部 jobs；不上传）
- [ ] 上传 zip 的 `jobs/` **含齐**：`baseline|nop` + `oracle` + 一个完整达标的 16-trial 难度 batch 及 `difficulty-manifest.json`；smoke 有则带、无则可不含
- [ ] 上传 zip **无**无关失败 batch / `_full_job_backups` / `_auto_loop_state`；交付 batch 不删除或隐藏任何 trial；失败 batch 的原始数据仍在本地全量备份中
- [ ] 每个难度 batch 固定 16 容器、同一提示词、同一冻结修订；提交的**同一完整 batch**恰好 16 条，`reward<1` ≥13、`reward=1` ≥1；每条均有 reward 且无超时污染
- [ ] 任务级 manifest 已保留每批完整结果；每个 batch 均列出所有 trial 的终态/reward/来源，未因样本选择删除或改写证据
- [ ] 没有因 `reward=1` 数量提前停止 batch；每批均完整结束 16 路
- [ ] 难度 job **无超时污染**：timeout/cancel 的 0 → 整 job 作废重跑后再打包
- [ ] 质检综合分目标 ≥ 0.7（见 [qc-scores.md](qc-scores.md)）
- [ ] `instruction.md` **无 AI 痕迹**（见 [instruction-style.md](instruction-style.md)）；默认 **level4**（过难降级交付可为 level3）
- [ ] 扩展包全部钉版本；含 `pytest-json-ctrf`；`test.sh` 有 `--ctrf`（[notes-22.md](notes-22.md) a/B）
- [ ] tests 为 `test_outputs.py` + `test.sh` + `quality.toml`（无 `checks.py`）
- [ ] 上传 zip 含合规 `jobs/`；无 `.DS_Store`
- [ ] `domain` / `subdomain` 为官方枚举原文（[domain-taxonomy.md](domain-taxonomy.md)）
- [ ] `task_type` 与提示词一致；同仓多题未打同一模块（H/I）
- [ ] `tests/quality.toml` 含 `[judge]` 与 ≥2 条任务相关 `[[criterion]]`
- [ ] `quality.toml` **不是** 仅有 `[quality]` / `version = 1` 空壳
- [ ] `tests/test.sh` 在确定性通过后调用 `uvx --from harbor-rewardkit==… rewardkit`
- [ ] Dockerfile 提供 `uv`/`uvx` 并预热同一 pin 的 rewardkit
- [ ] 每个重启 batch 前均已复用或重建镜像：记录 `docker image inspect` 的 digest，并实际验证 Agent CLI、RewardKit 与最小项目测试；环境/题目/验证器变更后已重新校准

## 结构与安全

- [ ] 新题/重跑前已做 **Docker 环境清理**（自身网络池/残留容器；见 SKILL）
- [ ] 若本作业有多次换仓目录：交付 zip 来自 **最新 `-YYYYMMDD-HHMM` 时间戳** 目录（除非用户点名旧版）
- [ ] zip 根目录唯一：`<task-name>/`（与交付目录名一致，含时间戳后缀若有）
- [ ] 含 `instruction.md`、`task.toml`、`environment/`、`solution/`、`tests/`
- [ ] workspace 无 `.git`、无 solution/tests、无密钥
- [ ] 无 `_auto_loop_state`、失败 rounds、`_failed_project_backups`、本地 `scripts/` 控制器
- [ ] jobs 日志/config 已脱敏（无 `sk-` / 明文 API key）
- [ ] 交付修订哈希与校准 + 难度门所用修订一致

## 建议命令

```bash
TASK=<task-name>
ASSIGN=<作业ID>
FULL=task/_full_job_backups/${ASSIGN}/${TASK}-full-$(date +%Y%m%d-%H%M)
ZIP=task/${TASK}.zip

# 1) 全量备份（含全部 jobs）
mkdir -p "$(dirname "$FULL")"
rsync -a --exclude '.DS_Store' "task/${TASK}/" "$FULL/"

# 2) staging：jobs 保留 baseline|nop + oracle + 一个完整达标难度 batch + manifest（smoke 可选）。
#    任务级 manifest 必须能映射回每个 batch 的所有原始 trial。

# 3) 硬自检：baseline+oracle 必须在 zip 内；smoke 不强制；quality 非空壳；test.sh 接 rewardkit
unzip -l "$ZIP" | rg -q 'jobs/(baseline|nop)/' || { echo 'FAIL P0-1 baseline'; exit 1; }
unzip -l "$ZIP" | rg -q 'jobs/oracle/' || { echo 'FAIL P0-1 oracle'; exit 1; }
unzip -p "$ZIP" '*/tests/quality.toml' | rg -q '\[\[criterion\]\]' \
  || { echo 'FAIL P0-2 empty quality.toml'; exit 1; }
unzip -p "$ZIP" '*/tests/test.sh' | rg -q 'harbor-rewardkit' \
  || { echo 'FAIL P0-2 no rewardkit'; exit 1; }
echo 'OK zip P0 gates'
```

## 自检 PASS 之后

1. 按 [feishu-delivery.md](feishu-delivery.md) **自动回写飞书**  
   （标注员 + 文本 + 四列 + zip + 状态已提交 + 修改日期；**不写标注日期**）  
2. 再按 [continuous-queue.md](continuous-queue.md) **零确认**领下一题（向威+已领取；无则停挂机；失败题按 skill 自动换仓勿问用户）
