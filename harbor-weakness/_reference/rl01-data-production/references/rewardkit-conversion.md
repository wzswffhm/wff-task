# rubrics.json → tests/rubrics.toml（Harbor 落地口径）

`rubrics.json` 是出题侧的原始评分细则（可含负 weight、可含 `levels`）；Harbor 真正读取的是
`tests/rubrics.toml`。两者字段不同名、负分表达方式不同，**转换是最容易整题退回的一步**。
用 [../scripts/gen_rubrics_toml.py](../scripts/gen_rubrics_toml.py) 生成，不要手写。

## 一、字段映射

| rubrics.json | rubrics.toml | 说明 |
|---|---|---|
| `id` | `id` **且** `name` 与之逐字相同 | 只写 `id` 会让纯中文 description slugify 成空串，全部条目键塌缩、解析崩溃 |
| `description` | `description` | 末尾必须追加 `Deliverables to inspect: \`output/<文件名>\`.` |
| `type: Gradient` | `type = "likert"` + `points = 5` | 档位固定 5 档 |
| `type: Binary` | `type = "binary"` | — |
| `weight > 0` | `weight` 原值 | 只允许 3.0 / 7.0 / 10.0 |
| `weight < 0` | `negate = true` + `weight = abs(值)` | **不得写负 weight** |

## 二、四个必须记住的坑（都实际导致过退回）

### 1. 扣分项必须 `negate = true`，不能写成"未违规得分"

- 写负 weight：平台聚合脚本判为异常条目并剔除，`verifier_error = 1`，整次评分作废。
- 写成"未违规则得分"的正向条：扣分项被计入满分分母 `S_max`，虚增基准，且违规时只是"不得正分"，
  不主动扣分——语义与设计不一致。
- 正确写法：`negate = true` + 正 weight，description **直接描述违规行为**（不需要改写句式）。

### 2. likert 只允许一套标度：1–5 整数

description 里**只能**出现 `评分为 1–5 整数：5=…；4=…；3=…；2=…；1=…。`。
历史上出现过同一 description 同时留了旧的 `按下列档位评分：1=…；0.75=…；0=…`（0–1 标度），
两套标度方向相反（0–1 里 1 最好、1–5 里 1 最差），判官会输出小数被 schema（integer）拒掉，
或随机漂移。**旧的档位段必须从 description 里删掉。**

### 3. `levels` 是锚点唯一来源，且必须与设计意图一致

`Gradient` 的 5 档锚点由 `levels` 生成，映射固定：`1→5、0.75→4、0.5→3、0.25→2、0→1`。

- 若 description 里另写了一段档位文字，两者必须语义一致；不一致时**以 description 的档位段为准**
  重建 `levels`，然后删掉 description 里的那段（甲方明确要求"考点内容不需要把分档内容写出"）。
- 曾出现 `levels` 相对 description **整体错位一档**（`levels["0.75"]` 实际是 1 档的语义、
  缺最高档描述），判官据此给分，分数区间整体失真。生成前先跑
  [../scripts/validate_rubrics.py](../scripts/validate_rubrics.py) 的锚点一致性检查。
- `Gradient` 条目**不允许**没有 `levels`：那会得到一条只有引导语、没有档位的条目。

### 4. description 只写一次交付物清单，且不留空

每条 description 末尾恰好一段 `Deliverables to inspect: \`output/…\`。`：

- 多段 → 判官误判；
- 空的 `` ` ` ``（转换脚本取不到 artifacts 时的产物）→ 判官找不到交付物；
- 衔接处不要出现 `。。`、`。；` 这类重复标点（旧转换脚本遗留）。

## 三、其他硬写法

- `[judge]`：`judge = "claude-code"`、`prompt_template = "prompt.md"`、`model = "qwen3.7-plus"`、
  `timeout = 7200`、`weight = 1.0`、`mode = "individual"`，照抄不改。
- `[scoring]`：`aggregation = "weighted_mean"`。
- `tests/prompt.md` 用 rewardkit 模板原文（Material map / Reference-solution policy /
  Tool usage / **Fairness anchor** / `{criteria}`）；可以追加任务专属的 `[How to inspect]` 工具提示，
  但**不要**自写 `[Output]` 之类评分宽严表述，也不要删 Fairness anchor。
- 全文 LF、无 U+00A0 / U+3000 等不可见空白；`prompt.md` + 全部 description < 100 KB。
- `solution/solve.sh`、`tests/test.sh` 必须是 LF 且带可执行位（打进 zip 时用 0755 存）。
- 交付物文件名在**六处逐字节一致**：`instruction.md`、`[[metadata.deliverables]].path`、
  `artifacts`、`solution/golden_output/`、`tests/__golden_output/`、criterion 的交付物清单。
- 每条 description 必须同时说清**判什么**（可观察锚点）和**在哪判**（交付物路径）；
  多交付物题目逐条写全该条涉及的交付物，不要只写目录。

## 四、自检

```bash
python scripts/gen_rubrics_toml.py <task-dir>
python scripts/validate_rubrics.py <task-dir> [<task-dir> ...]
```

`validate_rubrics.py` 会核对 json/toml 条数与正分池一致、negate 集合一致、标度唯一、
锚点一致性、维度名在固定清单内、内容质量占比、禁字符与换行。
