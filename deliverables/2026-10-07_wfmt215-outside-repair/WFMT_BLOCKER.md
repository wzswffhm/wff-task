# wfflab__wfmt-215 资格门禁 · 阻塞报告

- 发现时间：2026-10-07 15:54（用户指令「125 进度如何，监控一下」→ 排查时发现）
- 结论：**215 的候选模型跑分（candidate 模式）从设计上无效，必须先修 harness 才能继续。控制组（no-change / golden）不受影响。**
- 217 的既有结论**不受影响**（理由见 §3）。

## 1. 直接证据：agent 自述被工具白名单挡住

QWEN run01（tag `wfq`，14:14:52 起）跑出的工作区快照里，agent 主动写了
`view/environment/workspace/WReparse/NOTES.md`：

> 本次会话的系统提示要求修改 `C:\task\environment\workspace\WReparse`（一个 PowerShell 模块），
> 并遵守 `...\docs\REPARSE-CONTRACT.md`。**这两者在容器里都不存在**：
> `list_dir ...\workspace` → `assets/ docs/ tests/ wfmt/ pyproject.toml README.md`
> `read_file ...\docs\REPARSE-CONTRACT.md` → `no such file`
>
> 而 `write_file` 被硬性限制在 `...\WReparse` 之下：
> `write_file ...\workspace\wfmt\varint.py` →
> `ERROR: only paths under C:\task\environment\workspace\WReparse are writable`
>
> 因此**无法直接就地修复 `wfmt/`**。

agent 只好把整份修复版源码写进自己新建的 `WReparse/` 目录，期待"有人在有写权限的会话里 xcopy 覆盖过去"。
**判分看的是 `case/environment/workspace/wfmt/`，那里从未被改动 → 必然 0 分。**

agent 还记录了两条能力缺口：

- `read_file` 只支持 UTF-8，对 `assets/sample.wfmt` 返回 `file is not valid UTF-8 text` → **看不到权威样本的字节**；
- 容器内无执行/测试手段 → 无法自查。

## 2. 根因：`runner.py` 把 217 的路径写死

`deliverables/2026-10-04_outside-harbor-win/runner/runner.py` 中硬编码了 7 处：

| 行 | 内容 |
|---|---|
| 264-265 | `mirror_workspace()`：回写 `view/…/WReparse` → `case/…/WReparse` |
| 275 | `workspace_fingerprint()`：指纹根 = `…/workspace/WReparse` |
| 361 | `list_dir` 工具示例路径 |
| 380 | `write_file` 工具描述："Only paths under …\WReparse are writable" |
| 406 / 411 | `SYSTEM_PROMPT`：PowerShell 模块路径 + 只允许写 `WReparse` |
| 446 | `WRITABLE_SUBPATH = environment/workspace/WReparse` |
| 489 | 拒绝写入时的错误文案 |
| 513-516 | 初始 user message：`…\docs\REPARSE-CONTRACT.md` + `…\WReparse` |

`SYSTEM_PROMPT` 还写死了"senior Windows/PowerShell engineer""Target Windows PowerShell 5.1"——
而 215 是 **Python 包**，契约文档是 `docs/FORMAT.md`（且题面明确说它是**过时草稿**，权威依据是 `assets/` 下的二进制样本）。

## 3. 影响面判断

| 项 | 是否受影响 | 说明 |
|---|---|---|
| 217 的历史门禁结论 | **否** | 217 的模块目录名恰好就是 `WReparse`，硬编码与之相符；`_r12gs.json` 的 `qualified=true` 继续有效 |
| 215 的 controls（no-change×3 / golden×3） | **否** | 这两条路径不经过 agent 工具白名单（no-change 不改文件，golden 跑 `solution/solve.ps1`）；产物完整（`result.json`/`checks.json` 齐全） |
| 215 的候选跑分（QWEN / OPUS / GLM / KIMI） | **是，全部无效** | agent 无法写 `wfmt/`，结果为结构性 0 分，**不是模型能力信号** |

## 4. 已执行的止血（15:56–15:58）

| 动作 | 结果 |
|---|---|
| `Disable-ScheduledTask oh-wfmt-qwen` | `state=Disabled`，触发器停在 2027-01-05 |
| 杀 runner 进程 | python pid 84016（14:14:52 起）已终止 |
| 删容器 | `oh-20261007t141452-candidate-qwen3-8-max-0902-01` 已 `docker rm -f` |
| 核查 runs 污染 | `runs/wfflab__wfmt-215/20261007T141452-…` **无 `result.json`** → `summarize_model_runs.py` 不会采信 |

无效轮的现场证据保留在
`runner/work/20261007T141452-candidate-qwen3.8-max-0902-01/view/environment/workspace/WReparse/NOTES.md`。

## 5. 后续选项

| 方案 | 内容 | 代价 | 备注 |
|---|---|---|---|
| **A. 参数化 runner** | 把模块目录 / 契约文档 / 语言提示从题包 `task.toml`（`[policy].mutable_paths`、`[task].workspace`）动态推导；给 `read_file` 增加二进制 hex dump 能力 | 改 7 处 + 新增 1 个工具；217 行为保持不变（默认值仍解析为 `WReparse`） | 任何"第 2 题"都需要这套能力，属于必要基础设施；改完需重跑 215 全矩阵（controls 可复用，仍需 2–3h） |
| **B. 换题** | 改选一道与 217 同型（**纯源码推理可解、无需读二进制样本、无需执行**）的 Windows 题 | 选题 + 范式整改 + 全矩阵跑分 | 候选题需从 `harbor-windows/` 其余 17 题里按"历史 QWEN 非满分 + 题面不依赖样本字节"筛 |
| **C. 修 215 题面** | 把权威布局（字节序 / CRC 变体 / 无填充）直接写进 `instruction.md` 或 README，摆脱对 `assets/` 的硬依赖 | 等于出**新题**，controls 与历史分全部作废 | 会显著降低难度，可能失去区分度 |

**时间判断**：本轮"10-07 18:00 前交付"的窗口内，A/B 都难以完成（修 harness ~1h + 跑分 2–3h）。建议按 A 修好基础设施、215 顺延，而不是带着无效数据继续推。

## 6. 一句话

215 的 QWEN 探针**不是模型做不出来，是它根本没被允许做题**——`runner.py` 是 217 专用的（模块名、语言、契约文档全写死），任何换名/换语言的题在它下面都会得到结构性 0 分。
