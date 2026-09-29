# no-skill 判分结果分析与后续方案 — 2026-09-28-3-marshmallow-doc-diff

## 一、结果

`grade_manual_trae.py --mode no-skill` → **独立 verifier `reward=1`** → `status = needs_task_hardening`（exit 20）。

即：**Doubao-Seed-Evolving 在没有专家 skill 的情况下把这道题做出来了。**

按 `obm-task-production/SKILL.md` 步骤 7：no-skill 为 `reward=1` 时必须**返修题面 / verifier / 中文专家思路，生成全新版本再重跑两侧**；本地流水线因此在 no-skill 处中止，不会继续 with-skill。

## 二、证据（这次运行是真实的，不是误判）

| 项 | 值 |
|---|---|
| 工作区 | `trae-runs-v1/3-no-skill/3-no-repo` |
| HEAD | `80800558e279c28afda3b892f89b1669d3b106e9`（= 基线，未被污染） |
| no-skill prompt sha256 | `58b74633…`（= BASELINE，确认**未**夹带专家思路） |
| patch sha256 | `c99c103ee47070174b85a56f8fecebcc77dbb3b7fe6277cd03282ffd320f2832` |
| 改动 | `src/marshmallow/schema.py` **+305 行**（第 842 行起 `def document_diff`）；另自建 `tests/test_document_diff.py`（该自建测试被过滤，不参与判分） |
| 判分 | F2P 11/11 通过、P2P 826/826 通过 → reward=1 |

## 三、排除"我们的 F2P 太窄"这一解释

写过契约探针 `tools/probe_contract.py`，针对**公开契约中未被现有 11 条 F2P 覆盖**的行为，分别打在 Agent 实现与参考实现上：

| 探针 | 参考实现 | Agent 实现 |
|---|---|---|
| 01 输出顺序跟随 `schema.fields` 声明顺序（b,a）而非输入顺序 | `["b","a"]` | `["b","a"]` ✅ |
| 02 `include_unknown=True` 纳入未知键 | `[("change","z")]` | 同 ✅ |
| 03 内容相同但键序不同 → 空列表 | `[]` | `[]` ✅ |
| 04 `ignore_fields` 在**嵌套层**同样生效 | `[]` | `[]` ✅ |
| 05 纯函数（不改输入、不改 schema.fields） | 全 true | 全 true ✅ |
| 06 `List(标量)` 按位置 `add` + 下标正确 | `[("add","tags[2]",3)]` | 同 ✅ |

**两者完全一致** → 说明该实现是真正确，而非被弱测试放过。题目偏简单是**真实难度不足**。

### 加强探针（第二轮，8 项更难的边界）—— 仍然零分歧

`tools/probe_contract_hard.py` 追加了更难的边界，Agent 与参考实现**逐项输出完全相同**：

| 探针 | 结果（两者一致） |
|---|---|
| H1 `Nested(many=True)` 元素变少 | `[("remove","members[1]",{...},None)]` |
| H2 三层嵌套路径 | `[("change","a.inner.c",1,2)]` |
| H3 `List(Nested)` 元素新增 | `[("add","items[1]",None,{...})]` |
| H4 混合 schema 输出顺序 | `["b","n.y","t[0]"]`（= 声明顺序） |
| H5 顶层字段只在一侧 | `[("remove","x",1,None)]` |
| H6 `ignore_fields` 在 many 元素内部 | `[]`（生效） |
| H7 值 1 → None | `[("change","x",1,None)]` |
| H8 两侧都是 None | `[]` |

**合计 14 项契约行为无障碍、零分歧** → 结论：**该实现已完整满足公开契约。**

### 由此得到的硬结论

- **只加强 verifier 不足以硬化**：凡能从现有契约推导出的行为，Agent 都做对了；补测不会让它失败。
- 要制造区分度，**必须改动任务本身**（新增/收紧契约要求），而契约一变，prompt 就变 → 两侧都要用新题重新跑。

### 根因判断

`C_agent_task` 把可观察契约写得非常完整（签名、op 语义、path 语法、遍历顺序、Nested/many/List 递归规则、未知键策略、纯函数要求），几乎等同于把算法讲清；强模型只需"照着实现"。契约清晰本身是规范要求（否则会触发"只能猜契约"的拒收项），所以**难度不能靠模糊契约来加，只能靠提高任务本身的推理要求**。

## 四、两条规范口径（结论不同，需你裁决）

| | 本地 `obm-task-production` 流程 | 需求方《OBM Source 收集说明书》"数据质量评价" |
|---|---|---|
| 定位 | no-skill=1 视为必须返修 | 第 2 条属"内部检测、质量激励"，**非硬门禁** |
| 后果 | 停止 with-skill，返修出新版本重跑 | 记为 `not_met` 即可，**不阻止打包与提交** |
| 依据 | `SKILL.md` 步骤 7 | `requirements-and-gates.md`：第 2 条未达成"不得阻止打包和飞书提交" |

> 注意：即便按需求方口径，本地 `capture_final_check.py` 仍会因 `no_skill.reward != 0` 判 `ok=false`，从而挡住 `build_delivery_zip.py`。要按此口径交付需放宽该检查。

## 五、硬化方向

> 前提已由探针确定：**纯 verifier 补测无效**（Agent 在 14 项契约行为上全对）。因此必须**改动任务契约**，代价是 prompt 变化 → 两侧都要用新题重跑一次 Trae。

按性价比排序：

1. **叠加耦合的第二能力（推荐，中成本）**：在原 `document_diff` 之外，要求实现配套的**反向应用** `Schema.apply_diff(document, records)`，并把行为断言写进契约：
   - `apply_diff(left, document_diff(left, right)) == right`（往返一致）；
   - 未知字段 / 类型冲突 / 非法 path 时返回结构化错误（或抛指定异常）而非静默改坏；
   - 重复应用幂等；`apply_diff` 同样为纯函数。
   难点在于 diff 与 apply 必须**语义自洽**（`add` 的 `left=None` 语义、列表 `[i]` 位置语义、`ignore_fields` 下如何回填），且不能靠单侧实现糊过去。
2. **引入 schema 演变（中成本）**：diff 需跨两个**字段集不同**的 schema（含 `data_key` 重命名、字段增删、`attribute` 差异），路径与忽略要区分"序列化键"与"声明名"。契约可完整声明，但实现需要字段映射与顺序合并，推理量明显上升。
3. **加规模/性能约束（低成本但偏工程）**：对 10 万元素级别的列表要求线性时间与内存上限；逼迫避免朴素深拷贝与 O(n²) 比较。可观察（超时/超内存即失败），但"工程味"重于"推理味"。
4. ~~加强 verifier~~：**已验证无效**，仅可择机作为回归补充（把 14 项探针里尚未进 F2P 的行为补上，防止未来实现退化），但不能指望它翻转 no-skill。

### 成本对比

| 方案 | 我这边的工作量 | 你需要的工作量 |
|---|---|---|
| 硬化（任一方向）+ 重跑 | 改契约/参考实现/verifier/skill + 生成 `trae-runs-v2` | **2 次 Trae 运行**（no-skill、with-skill） |
| 按需求文档口径交付 | 放宽本地打包门禁 + 补 FINAL_CHECK/打包说明 | 0（仅飞书提交） |

## 六、当前状态（未提交、未打包）

- `EXPERIMENT_RESULT.json` = `needs_task_hardening`（真实记录，未伪造）。
- 未生成 `FINAL_CHECK.json`、未打包、未做飞书提交。
- 旧工作区 `trae-runs-v1` 保留（不覆盖）；硬化后应生成 **`trae-runs-v2`** 重跑。
