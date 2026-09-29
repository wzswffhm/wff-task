# 验证报告（除 Trae 外全量）— 2026-09-28-3-marshmallow-doc-diff

本报告汇总在**跳过 Trae 双跑实验**的前提下，对题包执行的全部可自动化验证。结论：
**除「依赖 Trae 实验结果」的两道门禁外，其余验证全部通过。**

## 一、总览

| # | 验证 | 工具 | 结果 | 说明 |
|---|---|---|---|---|
| 1 | proposal schema/字段校验 | `obm-review-skills/scripts/validate_proposals.py` | ✅ PASS | `[OK] 1 passed, 0 failed` |
| 2 | proposal（skill 内置副本）校验 | `obm-task-production/proposal_validator/validate_proposals.py` | ✅ PASS | 与 #1 同源；**要求目录名为 `deepSWE_<proposal_name>`** |
| 3 | 中文专家 skill 语言检查 | `check_skill_language.py` | ✅ PASS | 汉字 2151 / 英文字母 211 / 中文说明行 51/51 |
| 4 | 包静态预检（Windows） | `check_package.py` | ⚠️ 2 FAIL | 仅 `test.sh`/`grader.py` 可执行位（NTFS 限制，非缺陷） |
| 5 | 包静态预检（Linux ext4） | `check_package.py` | ✅ PASS | exec 位可设，`0 errors, 1 warning` |
| 6 | 场景重合召回 | `check_scene_overlap.py` | ✅ 无重合 | 扫 113 题；最高分是本题自身 registry 记录 |
| 7 | NOP / Oracle（本地） | `run_local_verifier.py` | ✅ 0 / 1 | 11 F2P + 826 P2P |
| 8 | NOP / Oracle（离线 Docker，手工契约复现） | `docker build/run --network=none` | ✅ 0 / 1 | 见 `docker-wsl-evidence.md` |
| 9 | NOP / Oracle（**官方编排器** `verify_agent_patch.py --docker`） | 同上 | ✅ 0 / 1 | 见 `official-docker-verify/` |
| 10 | 最终质检编排器 | `capture_final_check.py` | ⛔ 门禁 | 3 项静态子检查全 PASS，仅「实验结果」缺失而 FAIL |
| 11 | 交付 ZIP 打包 | `build_delivery_zip.py` | ⛔ 门禁 | 无实验结果 → 正确拒绝（exit 1） |
| 12 | Trae no-skill / with-skill 双跑 | `grade_manual_trae.py` | ⏸ 跳过 | 需 Trae GUI，用户自行执行 |

## 二、关键证据

### 1) 官方 Docker 编排器（`verify_agent_patch.py --docker`）

- NOP（`sources/app` 保持基线 + 空 patch）：`{"status":"completed","stage":"grade","container_exit_code":0,"reward":0}`
  - F2P 0/11，P2P 826/826
- ORACLE（`sources/app` 预先应用 `reference.patch`）：`{"status":"completed","stage":"grade","container_exit_code":0,"reward":1}`
  - F2P 11/11，P2P 826/826
- 两次构建/运行均 `--network=none`，容器内 `test.sh` 写出 `/logs/verifier/reward.json`，编排器读取判分。
- 证据目录：`official-docker-verify/{nop,oracle}/{VERIFICATION.json,VERIFIER_RUN.log,logs/reward.json,artifacts/model.patch}`。

> **重要语义（已修复）**：原 `verify_agent_patch.py` 只从 `sources/app` 构建 app 镜像，**不会**把 `--patch` 应用到 `/app`，导致判分恒为基线（with-skill 永远 0）。已修复：现在会把 patch 的 `marshmallow/` 源码段应用到一份 `sources/app` 暂存副本后再构建。修复过程与验证见 `PIPELINE-FIXES.md`。下面 ORACLE=1 是**在修复前**用“预先打好补丁的 sources/app”得到的；修复后用原始包 + `reference.patch` 同样得到 1（见 `PIPELINE-FIXES.md` 验证表）。

### 2) `capture_final_check.py`（Linux ext4，目录名规范）

`exit_codes: [0, 0, 0, 1]`

- `[0]` check_skill_language → **PASS**
- `[1]` proposal_validator（skill 内置）→ **[OK]**
- `[2]` check_package（Linux）→ **PASS (0 errors, 1 warnings)**
- `[3]` 实验结果校验 → **FAIL**：`EXPERIMENT_RESULT.json` 不存在（Trae 未跑）

→ `FINAL RESULT: FAIL`，**仅**因缺 Trae 实验；三项静态检查全部通过。

### 3) `build_delivery_zip.py`

```
实验结果不存在：/root/obm-check/EXPERIMENT_RESULT.json
EXIT=1
```
门禁正确，未生成任何 ZIP。

### 4) `check_package.py` 在两种文件系统下的差异

| 环境 | test.sh/grader.py 模式 | 结果 |
|---|---|---|
| Windows NTFS | `0o666`（无法设 exec 位） | FAIL×2 |
| Linux ext4（chmod +x 后） | `0o755` | PASS |

结论：Windows 的两个 FAIL 纯属验证环境限制；verifier Dockerfile 的 `RUN chmod +x` 在容器内补齐，运行时不受影响。

## 三、结论与后续

**已通过（除 Trae 外全部可自动化验证）**：proposal 校验、中文 skill、包预检（Linux）、场景重合召回、NOP=0/Oracle=1（本地 + 离线 Docker + 官方编排器）。

**判分链路修复（本报告后续补充）**：发现并修复两处会让 with-skill 恒为 0 的缺陷——(1) 编排器从不应用 Agent patch；(2) NTFS 工作区换行符污染使 `create_patch` 产出垃圾 patch。详见 `PIPELINE-FIXES.md`。

**3、4 已做成自动化**：`tools/run_post_trae.sh` 一条命令串起 no-skill 判分 → with-skill 判分 → FINAL_CHECK → 打包 → 对 ZIP 再跑 check_package，并带“工作区无改动即中止”的保护。用法见 `TRAE-RUN-SOP.md`。

**仅剩 Trae 双跑需人工（GUI）**：

1. Trae 里跑 no-skill → `run_post_trae.sh no-skill`，期望 reward=0；
2. Trae 里跑 with-skill → `run_post_trae.sh all`，期望 reward=1 → `status=passed` → `FINAL_CHECK.json.ok=true` → 出正式 `.zip`；
3. 飞书提交。

> Trae 无可用无头 CLI（`traecli` 需企业旗舰套餐，且 OBM 规范禁止 Codex 驱动 Trae），故双跑必须由你在 GUI 完成；其余全部已自动化。
