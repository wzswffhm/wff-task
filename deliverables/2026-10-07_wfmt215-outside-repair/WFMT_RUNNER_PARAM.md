# Outside Harbor runner 参数化修复报告

> 2026-10-07 16:20–16:38 ｜ 触发原因：`wfflab__wfmt-215` 的候选跑分被判定为**结构性无效**

## 1 症状

215 的 QWEN 探针（tag `wfq`，14:14:52 起跑）跑了 1h40m 也没产出有效结果。模型自己在工作区写了
`NOTES.md` 自述：

> 系统提示要求改 `…\workspace\WReparse` 并遵守 `docs\REPARSE-CONTRACT.md`，但容器里这两样都不存在……
> `write_file …\workspace\wfmt\varint.py` → `ERROR: only paths under …\WReparse are writable`

即：**agent 从头到尾没有被允许修改题目要求它修改的 `wfmt/`**。判分看的是 `wfmt/`，那里一个字节没动
→ 任何候选模型都必然是 0 分。这不是模型能力信号，是**跑分基础设施缺陷**。

## 2 根因

`deliverables/2026-10-04_outside-harbor-win/runner/runner.py` 把 `wfflab__wreparse-217` 的
题目特征**硬编码**了 8 处：

| # | 位置 | 硬编码内容 | 对 215 的后果 |
|---|---|---|---|
| 1 | L17 docstring | `edit environment/workspace/WReparse` | 仅文档 |
| 2 | `mirror_workspace()` | `WReparse` | 回写错目录，agent 改动全丢 |
| 3 | `workspace_fingerprint()` | `WReparse` | `changed_workspace` 恒 False |
| 4 | `list_dir` schema | 示例路径 `…\WReparse` | 误导模型 |
| 5 | `write_file` schema | "only paths under `…\WReparse`" | 误导模型 |
| 6 | `SYSTEM_PROMPT` | PowerShell 人设 + `WReparse` + `REPARSE-CONTRACT.md` | **模型被指向不存在的文件/目录** |
| 7 | `WRITABLE_SUBPATH` / `is_writable()` | `environment/workspace/WReparse` | **写白名单挡住真正的源码** |
| 8 | 首轮 user prompt | `REPARSE-CONTRACT.md` / `WReparse` | 同上 |

另有一个隐藏缺陷：`tool_read_file()` 只按 UTF-8 解码，而 215 的题面明确说
`assets/*.wfmt` **二进制样本才是唯一权威依据**（`docs/FORMAT.md` 是过时草稿）——旧 runner 连样本都读不了。

## 3 修复

### 3.1 从 task.toml 推导 profile（不再有任何题目硬编码）

新增 `resolve_task_profile(task_dir)`，读取：

- `[policy].mutable_paths[0]` → 可写模块（`environment/workspace/wfmt`）
- `[policy].read_only_paths` 里以 `/docs` 结尾的项 → 参考文档（`environment/workspace/docs/*.md`）
- `[metadata].tags` / 模块内文件后缀 → 语言人设（`powershell` / `python`）
- 存在 `environment/workspace/assets/**` 时 → 标记二进制样本目录

缺失字段时的兜底：`mutable_paths` 为空则自动探测 workspace 下第一个非 `docs/assets/tests` 的子目录；
语言无法判定则按模块后缀推断，最终兜底 PowerShell。**`DEFAULT_PROFILE` 的默认值即 217 的原设定**，
所以 217 行为零变化。

### 3.2 二进制读取

`read_file` 现在检测二进制（含 NUL 或非 UTF-8）并返回 **hex dump**（16 字节/行，上限 64 KB），
这样模型才能对样本字节做推理。`write_file` 白名单、`mirror_workspace`、`workspace_fingerprint`
全部改为跟随 profile。

### 3.3 并发唯一性（新增，见 §5）

## 4 验证

`_verify_runner_param.py`（不依赖 Docker，纯逻辑 + 真实目录拷贝）：

| 检查 | 217 | 215 |
|---|---|---|
| 模块 | `WReparse` | `wfmt` |
| 语言人设 | PowerShell | Python |
| 参考文档 | `docs/REPARSE-CONTRACT.md` | `docs/FORMAT.md` |
| 样本目录 | — | `assets/` |
| 写白名单：模块内 | **ALLOW** | **ALLOW** |
| 写白名单：docs / assets / instruction | deny | deny |

端到端链路（真实 `build_agent_view` → 模拟改文件 → `mirror_workspace` → `workspace_fingerprint`）：

- view 中 `wfmt/` 就位 ✓
- 指纹前后变化 `True` ✓
- 改动正确回写到 case ✓
- `assets/sample.wfmt` 309 字节逐字节保真 ✓
- hex dump 输出正常（首行即 `57 46 4d 54` = `WFMT` 魔数）✓

## 5 附带的并发缺陷（并行跑分必须修）

首次并行起 3 个 QWEN 分片时**三个全部秒退**：

```
RUN FAILED: [WinError 3] 系统找不到指定的路径。:
  …\work\20261007T163549-candidate-qwen3.8-max-0902-01\case\environment\workspace
```

原因：`run_id` 由 `{秒级时间戳}-{mode}-{label}-{序号}` 组成。**同模型的两个分片在同一秒启动 →
run_id 完全相同 → 共用同一个 `work/` 目录和同一个容器名**，`copy_tree` 互相踩踏。

修复：`run_id` 追加 `secrets.token_hex(2)` 随机后缀。`summarize_model_runs.py` 用
`run_root.glob("*/*/result.json")` 定位结果、按 `result.json` 内的 `model_alias` 匹配模型，
`run_id` 仅作为文本记录 → 改格式零影响。

修复后三个分片正常并行：容器 `oh-…-f61d` / `oh-…-17c7` / `oh-…-2d61`，`Up` 正常。

## 6 影响面

| 项 | 是否受影响 |
|---|---|
| 217 既有结论（`qualified=true`） | **否** ✅ — 默认 profile 与硬编码值等价 |
| 215 的 controls（no-change×4 / golden×3） | **否** ✅ — controls 不走 agent 工具链 |
| 215 的候选跑分 | **是** — 旧轮全废（已删），修复后重跑 |
| 未来任何新题 | **是（正面）** — 只需 `task.toml` 齐全，无需改 runner |

## 7 变更清单

| 文件 | 变化 | sha256（前 16） |
|---|---|---|
| `runner/runner.py` | 参数化 + 二进制 + 唯一 run_id | `4698662eec3349f2`（42,079 B） |
| `…/scripts_backup/runner.py.pre_param` | 修复前备份 | `85968ca0c6baab03` |
