# 流水线缺陷与修复 — 2026-09-28-3-marshmallow-doc-diff

在处理「3 FINAL_CHECK / 4 打包」时，发现官方判分链路有两处缺陷会让 **with-skill 永远拿不到 reward=1**（进而永远无法交付）。已定位并修复，均经实验验证。

## 缺陷 1：`verify_agent_patch.py` 从不应用 Agent 的 patch

- **规范要求**（`references/deepswe.md` 第 17 行）：*“verifier 在独立、干净的环境中收集并应用 Agent patch。”*
- **实际行为**：`verify_agent_patch.py` 只把 `model.patch` 复制到 `output/artifacts/model.patch`（挂载到容器 `/logs/artifacts`，无人读取），然后 `docker build` 的是 **原始的 `sources/app`**，从头到尾没有 `git apply` / `patch`。
- **后果**：无论 Agent 改没改，判分环境都是基线 → F2P 全挂 → **reward 恒为 0**。no-skill 恰好“正确”（0），with-skill 被误判为 0 → 状态 `needs_skill_revision` → 无法交付。
- **复现证据**：对**未打补丁**的 `sources/app` 传入实现了 `document_diff` 的 `reference.patch`，得到 `reward=0`（修复后同输入得到 `reward=1`）。

### 修复
`obm-task-production/scripts/verify_agent_patch.py` 增加 `prepare_app_context()`：
1. 把 `sources/app` 复制到 `output/app-context/`；
2. 从 `model.patch` 中**只保留落在 `marshmallow/` 的源码段**（Agent 工作在完整上游树 `src/marshmallow/`，而 `sources/app` 是扁平包 `marshmallow/` 且没有 tests/、docs/、.github/，整份 patch 无法整体套用），并把 `src/marshmallow/` 重写为 `marshmallow/`；
3. `patch --dry-run -p1` 预检通过后再实际应用；
4. `docker build` 改用打过补丁的 `app-context`（镜像指纹也随之变化，避免复用基线镜像）。

### 验证（WSL 离线 docker）
| 输入 patch | 修复前 | 修复后 |
|---|---|---|
| 空 patch（= 无改动） | 0 | **0** ✓ |
| `reference.patch`（src/marshmallow 实现） | 0 ✗ | **1** ✓ |
| 混合 patch（marshmallow + tests/ + .github/ 噪声） | 0 ✗ | **1** ✓（噪声段被丢弃） |

## 缺陷 2：NTFS 工作区换行符污染导致 patch 是垃圾

- **现象**：`create_patch()` 用 `git diff --binary <baseline_head>` 生成 patch，但两个 Trae 工作区仓库在 NTFS 上**整棵树 95/95 文件都“被修改”**——工作树是 CRLF，基线 blob 是 LF，而 `core.autocrlf` 未设置，git 不做归一化。
- **后果**：生成的 `model.patch` 是 **50597 行全仓库换行符 churn**（每行 `-x` / `+x` 看起来一样），完全不是 Agent 的真实改动；即便拿去应用也必然失败。
- **复现证据**：`git status --porcelain` = 95 行；`@@ -1,1253 +1,1253 @@` 全文件替换；`diff <(git show HEAD:f) f` 显示 `+...^M`。

### 修复
- 给两个工作区仓库设 `git config core.autocrlf true`（工作树 CRLF 与 LF blob 归一化）。设置后 `git diff --name-only` = **0**，工作区干净。
- 在 `tools/run_post_trae.sh` 的 preflight 中强制执行该配置，并加“工作区无改动 → 判定 Trae 未跑并中止”的保护，避免在没有真实 Agent 产出的情况下误判。
- 恢复工作树用 `git checkout -f -- .`（Trae 尚未运行，无损失）。

## 附带修复（本轮早前）

- `sources/verifier/test.sh` 补写 `/logs/verifier/reward.json`（对齐 `verify_agent_patch.py --docker` 的读取契约）。
- `sources/verifier/wheels/` 补 `pygments` wheel（pytest 9.1.1 依赖，离线构建必需）。

## 仍受制于环境（非流水线缺陷）

- `sources/app` 是扁平包、Agent 工作区是完整上游树——这是 OBM deepSWE 题的既定约定（同题 `2026-09-28-2-diskcache` 亦然）。缺陷 1 的修复用“只取包源码段 + 路径重写”来适配，无需改动题包结构。
