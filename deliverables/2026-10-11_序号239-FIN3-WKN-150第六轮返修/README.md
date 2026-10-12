# 序号 239（FIN3-WKN-150）第六轮返修说明

- 飞书记录：Base `QpzNb4fXSamfX6sLloBcPfHNnug`，表 `tblPNrBtjFfwOowN`，记录 `reczz28Jf9pZeD1T`。
- 依据报告：`evidence/序号239_质检报告 (3).md`（快照 `20261011_112005`，检查对象 `work_fin-b01_20261006_fix7-150.zip`）。
- 批次：`work_fin-b01_20261006_fix8-150`；题包版本 `1.0.7 → 1.0.8`。

## 1. 四项【待改】的处置

| # | 报告要求 | 处置 |
|---|---|---|
| 5 | 修好 `reproduce.py` 的字符串插值并同步镜像，**从输入生成**同源参考产物 | 为退出回报段缺失 `f` 前缀的 4 个片段补 `f`（原先会输出 `{med_pe:.2f}` 等字面占位符）；`tests/__golden_output/` 同步为逐字节一致；随后在判分镜像内由脚本从 40 份只读输入生成产物，并以生成结果更新两份 golden |
| 6 | 补齐可核验的**新 Oracle 实际生成产物及执行/判分归档** | 生成命令、镜像、返回码、耗时、脚本 stdout 与 7 件产物 sha256 全部归档于 `oracle/轨迹/`（`generation.log` / `generation.json` / `generated_manifest.json`）；据此重判 Oracle |
| 7 | 补 `[scoring] aggregation="weighted_mean"` 等价配置 | `tests/rubrics.toml` 末尾追加 `[scoring]` 两行，未触碰任何 `[[criterion]]`；判据仍 36 条、权重与负项解释不变 |
| 8 | `交付文档.md` 置于**批次根**并校正文案 | 文档移至批次根（题目目录内不再放置）；重写当前状态章节（`fix8-150` / `1.0.8` / Oracle `1.000000` / 均分 `0.650758`）；更正被上一轮批量替换污染的历史标注（`R27` 变更归入 `1.0.6 → 1.0.7`，并在 §9.1 显式登记）；保留环境变量表与版本变更史 |

## 2. 参考生成闭环（本轮核心）

- **缺陷**：`reproduce.py` 第 834—837 行为普通字符串而非 f-string，运行时会输出字面占位符，与归档 golden 中已展开的 `16.12 / 18000 / 290160 / 6.50% / 18873 / 1.26 / 8.0%` 不符。
- **修正**：仅补 `f` 前缀（不改数值、措辞与判据），两份脚本 sha256 `8fbdca952fc3…` 逐字节一致。
- **真实生成**：判分镜像 `fin3-wkn-150:local` 内只读挂载输入，执行
  `python3 /solution/golden_output/FIN3-WKN-150_reproduce.py /app/input_files /app/output`，
  7 件产物齐全；生成备忘录 17,312 B / sha256 `72b47a936dd9…`，与两份 golden 及 Oracle 归档**四处逐字节一致**。
- **生成反馈驱动的三处补全**：逐轮重判把「判据明确要求、金标未明写」的缺陷逐处暴露并补齐。(a) `R11` 判 0——判据要求列示报告期**四期**非经常性损益（税后），金标此前只有 2025 年的 2,550；核对《11_非经常性损益明细.csv》后补列 2023 年 1,564、2024 年 1,768、2025 年 2,550、2026 年上半年 1,088。(b) `R19` 判 0——判据要求**明确指出**货币资金总额与有息负债构成，金标此前只给受限额与合计；补写「货币资金总额 25,000 万元（使用受限 3,500、可自由支配 21,500）」与「有息负债 20,000 万元（短期借款 12,000 + 长期借款 8,000）」。(c) `R32` 判 0——判据要求脚本从输入计算结论数值，原脚本把总股本 12,000 万股与第一大客户占比 36% 写成常量；现改为总股本从《34_股权结构、期权池与历史融资.md》股权结构表合计行读取、客户集中度从《23_收入明细_分客户_2025.csv》按营业收入降序计算（结果不变：12,000 万股 / 36.0%）。三处补全只把脚本已算出的输入数据写入正文或改为读入，不改结论数值、不引入新参数。
- **平台模板未动**：`solution/solve.sh` 保持平台固定模板（97 B / sha256 `3f26ac81cb1c4583…`，与 FIN3-WKN-149 逐字节一致），生成闭环由执行归档承载，不破坏模板一致性。

## 3. 判分结果

| 执行体 | 本轮 | 说明 |
|---|---:|---|
| `oracle` | **1.000000** | 产物重新生成后重判；36 条全满分 |
| `qwen3.8-max-0902` | 0.731818 | 沿用 fix7 归档值（判据未变，报告第 4 项确认无需重跑） |
| `gpt-5.6-sol` | 0.686364 | 同上 |
| `claude-opus-4-8` | 0.534091 | 同上 |
| **三模型均分** | **0.650758** | `429.5/660 = 0.6507575758 < 0.70` → PASS；难度维持 **A1** |

门禁：oracle `1.000000 > 0.85`；均分 `0.650758 < 0.70`；三模型非零；四场 `criteria_counted = 36`、`verifier_error = 0`。综合核验 **49 项全部通过**；`check_rubrics.py` / `check_package.py` 均 **[PASS]**。

## 4. 交付包与飞书终态

| 包 | 大小 | sha256 前缀 |
|---|---:|---|
| `work_fin-b01_20261006_fix8-150.zip`（批次，含批次根交付文档） | 14,089,171 B | `344b7c48ade8…` |
| `FIN3-WKN-150_task.zip` | 69,224 B | `5809dd16eb0f…` |
| `FIN3-WKN-150_answer.zip` | 931,488 B | `e486469ef7ee…` |
| `FIN3-WKN-150` 中的 `solution/golden_output` 与 `tests/__golden_output` | 各 7 项 | memo `72b47a936dd9…` / 脚本 `8fbdca952fc3…` |

批次包：顶层唯一 `work_fin-b01_20261006_fix8-150/`（根含 `交付文档.md`），第二层唯一题目目录 `FIN3-WKN-150/`；`.sh` 全 `0755`、其余 `0644`、全 LF、无 `_rejudge*` / `__pycache__` 残留、CRC 正常。

飞书回写（先删同名旧件、再传新件）终态：交付物 `work_fin-b01_20261006_fix8-150.zip`、题目附件 `FIN3-WKN-150_task.zip`、标准答案附件 `FIN3-WKN-150_answer.zip`，三字段**各恰好 1 个文件**；`状态` 仍为 **待返修**、`题目难度` 仍为 **A1**、`标注人` 仍为 **wff**，序号 / 质检报告字段未动，**未上传**任何机器报告或检查明细。

## 5. 文件清单

- `scripts/fetch_qc_report_239.py` — 拉取本轮质检报告并导出记录快照
- `scripts/scan_placeholder_bugs.py` — 占位符缺陷扫描
- `scripts/scan_rubric_values.py` — 36 条判据数值与金标的缺口对照
- `scripts/generate_oracle_150.py` — 容器内真实生成 + 执行证据归档
- `scripts/compare_generation_vs_gold.py` — 生成产物与 golden 差异比对
- `scripts/stage_fix8_batch.py` — fix8 批次组建
- `scripts/run_rejudge_150_fix8_wsl.py` — Oracle 重判驱动
- `scripts/archive_fix8.py` — 判分归档与 summary 重建
- `scripts/build_delivery_doc_fix8.py` — 批次根交付文档重建
- `scripts/refresh_doc_hashes.py` / `refresh_doc_hashes_v2.py` — 文档哈希与文案同步
- `scripts/repack_150_fix8.py` / `repack_task_answer_150.py` — 三包构建
- `scripts/verify_fix8_150.py` — 综合核验（49 项）
- `scripts/feishu_writeback_fix8_150.py` — 飞书附件回写（先删后传）
- `evidence/` — 质检报告、记录快照、生成产物与执行日志、判据数值扫描

