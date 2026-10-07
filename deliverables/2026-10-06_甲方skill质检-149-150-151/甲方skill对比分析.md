# 甲方 skill vs 自有 harbor-weakness skill 对比分析

对照对象：`Desktop/weakness-data-construction` v2.4（甲方出题）、`Desktop/weakness-qc` v1.0（甲方质检） vs `skills/harbor-weakness`（自有，delivery/00–08 + check_package.py）。

## 一、定位差异

| 维度 | 甲方 | 自有 |
|---|---|---|
| 拆分方式 | **出题与质检分离**（两个 skill，质检默认只读、只出整改单） | 出题+质检一体（check_package.py 既做生产自检也做交付门禁） |
| 版本管理 | SKILL.md metadata.version + CHANGELOG.md，脚本缺陷以版本记录（v2.3→v2.4 产物区间修复） | 无版本号，靠 07-pitfalls.md 沉淀 |
| 脚本哲学 | 脚本只覆盖机械可判定项，**规范原文 > 脚本**（`--self-test` 防脚本漂移） | 脚本门禁即门禁（#1–#15 全过才算 PASS），较少考虑"脚本本身错"的情形 |
| 知识形态 | 实证案例库（pitfall-cases 10 个真实案例，含"复算侧自己错"的反例） | 坑清单（B1–B11），多为正向规则 |

## 二、甲方有、我们没有的（值得吸收）

1. **`gen_rubrics_toml.py` 生成器**：rubrics.json → tests/rubrics.toml 单源生成，从机制上杜绝双文件不一致。我们手写双份，为此付出了 #4b 门禁 + 两轮整改的代价。
2. **json↔toml 一致性门禁**（validate_rubrics）：条数/正分池/negate 集合/likert 锚点一致性——与我们的 #4b 等价，但甲方更早、覆盖 likert levels 锚点一致性（我们未查 levels 错位）。
3. **`check_cross_model_concentration.py` 口径歧义检测**：三模型一致未满分且权重 ≥25% → 按口径歧义排查。我们完全没有这道门——"难度被歧义撑着"是最贵的打回原因。
4. **`check_rubric_style.py` 措辞门禁**：提问式判据/模糊量词/表格类定位语/Subjective 误标。我们只有 G3 结构校验，无措辞校验。
5. **`check_complexity.py --self-test`**：门禁脚本自带防漂移自检 + "规范原文 > 脚本"的冲突处置流程。
6. **`rejudge_by_docker.py`**：复用题包镜像只重跑判官（改判据/金标不重跑 agent）。我们用 harbor trial 重跑，成本更高。
7. **质检报告规范**：三档结论（必须整改/提示/已核实通过）、证据三件套（位置+原文+依据）、重跑决策表、"报告落 outputs/ 不进题包"。
8. **C1–C5 判定细则**：产物区间重叠取并集、申报档高于文件数档合法（我们按申报对齐即可，未细化到区间逻辑）。

## 三、我们有、甲方没有的

1. **平台模板逐字节复制**：test.sh（SHA 前缀 5920c204）/finalize.py（f528b27f）必须用平台 149/150 采用版——甲方 skill 未提平台模板版本管理。
2. **harbor 实跑工程链**：WSL/systemd-run/docker 排障、judge 死循环识别、verifier-only 重判、端点截断假分识别（我们的 07-pitfalls 大半是跑分工程坑，甲方 skill 不涉及）。
3. **飞书交付链路**：字段映射、附件替换、record-get 解析坑（甲方 skill 不含交付平台对接）。
4. **批次归档规范**：跑分产物与轨迹随批次归档、zip external_attr 显式写 0755、claude 日志脱敏。
5. **coverage 台账**：知识点去重（<3 道/知识点）、领域均匀分布——甲方配额脚本管 weakness 种覆盖，我们另管知识点粒度。

## 四、口径一致性核对（本次质检中实测）

| 口径 | 甲方 | 自有 | 一致性 |
|---|---|---|---|
| rewardkit 公式 | `(Σ正w·v − Σnegate w·(1−v))/Σ正w` | 同 | ✅ 12/12 复算一致 |
| 扣分项 TOML 表达 | negate=true + 正 weight，绝不写负 weight | 同 | ✅ |
| rubrics.json 负向 | 负 weight（+ negate 双标记——本次质检确认甲方脚本实际按负 weight 集合比对） | 负 weight + negate 双标记 | ✅（#4b 更严格，兼容） |
| 难度门槛 | oracle>0.85、均值<0.7、A1 0.6–0.7/A2 0.5–0.6/A3<0.5、至少一个非零 | 同 | ✅ |
| 三模型命名 | gpt-5.6-sol / claude-opus-4-8 / qwen3.8-max-0902 | 同（目录名一致） | ✅ |
| 轨迹框架 | claude-code 2.1.114 + steps | 同 | ✅ |
| 执行体目录白名单 | output/reward*.json/轨迹 | 同 | ✅ |

## 五、本次质检中被甲方脚本暴露的问题

1. **注释行含「negate = true」字面串** → 甲方 validate_rubrics 文本正则误吞进前条判据块 → 假 FAIL（150/151 已改注释修复）。教训：**给甲方脚本喂的文件要避免与甲方解析器耦合的敏感字面串**（他们用文本正则而非 tomllib）。
2. 甲方 check_package_permissions 按**批次包**口径校验任何 zip → 我们 task/answer 拆分包必报 FAIL（口径不符，非缺陷；交付时如被问可按此解释）。
3. 甲方 check_instruction_anchors 为**批次硬编码**脚本（锚点表写死 FIN-127/128/129-W），对其他批次不可用——锚点核对必须人工。

## 六、吸收建议（改自有 skill 的候选动作）

- 把「注释/描述避免含 `negate = true` 等甲方解析器敏感字面串」写入 07-pitfalls（已完成本轮 B12 候选）。
- 给 check_package.py 加 likert levels 锚点一致性检查（对齐 validate_rubrics）。
- 评估引入简化版集中度检查（三模型一致未满分权重占比 ≥25% 报警）。
- 考虑把 rubrics.toml 改为从 rubrics.json 生成（消灭双写）。
