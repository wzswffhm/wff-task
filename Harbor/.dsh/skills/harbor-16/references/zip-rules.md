## 打 zip 规则

Staging 后打包，zip 根目录必须是单一 `<task-name>/`。

**打包顺序（强制）：**

1. 难度门通过且 checklist 将 PASS 时 → **先全量备份**到  
   `task/_full_job_backups/<作业ID>/<task-name>-full-<时间戳>/`  
   （整题目录拷贝，含全部 jobs；密钥仍勿外传）
2. 再从当前 task 目录 **staging 精简包**：`jobs/` 拷齐  
   **baseline|nop + oracle + `selected-trials/` 下恰好 16 条入选 Trial + `difficulty-manifest.json`**（已有 smoke 可附带；未跑可不含）。提交 manifest 必须包含每条入选 Trial 的 source_job、trial_id、reward 和终态，以及 `selection_rule`；任务级 manifest 仍须保留所有原始 job 的完整索引，不能通过省略未入选数据改变结果含义。
3. 脱敏精简包内 API key → 打 zip → **打包后自检**（见下）→ 飞书只上传该精简 zip

**必须打进上传 zip：**

- 题目五件套 + `tests/{test.sh,test_outputs.py,quality.toml}`（**真实 rubrics，非空壳**）
- `jobs/baseline` 或 `jobs/nop`
- `jobs/oracle`（含 quality / rewardkit 执行证据）
- `jobs/selected-trials/` 下恰好 16 条入选 Trial 及 `difficulty-manifest.json`；manifest 必须完整说明跨 job 选样来源、原始 job 索引和选样规则

**可选打进上传 zip：**

- `jobs/*smoke*`（跑过则建议带上；**未跑不要求补跑**）

**禁止打进上传 zip：**

- `_auto_loop_state`、`_archive*`、`_full_job_backups`、失败难度 rounds
- `scripts/` 本地控制器、`_failed_project_backups/`
- `.git`、密钥、宿主机绝对路径、嵌套 zip
- 空壳 `quality.toml` 或未调用 rewardkit 的 `test.sh`

**打包后硬自检（任一条失败 = 禁止上传）：**

```bash
# baseline + oracle 必须在 zip 内（smoke 不检查）
unzip -l "$ZIP" | rg -q 'jobs/(baseline|nop)/' || { echo 'FAIL P0-1 baseline'; exit 1; }
unzip -l "$ZIP" | rg -q 'jobs/oracle/' || { echo 'FAIL P0-1 oracle'; exit 1; }
# 禁止空壳 quality（与质检 P0-2 对齐）
unzip -p "$ZIP" '*/tests/quality.toml' | rg -q '\[\[criterion\]\]' \
  || { echo 'FAIL P0-2 empty quality.toml'; exit 1; }
unzip -p "$ZIP" '*/tests/test.sh' | rg -q 'harbor-rewardkit' \
  || { echo 'FAIL P0-2 no rewardkit'; exit 1; }
```