---
name: wff-workspace-discipline
description: >
  wff-task 工作区落盘纪律。约束 Agent 的文件写入位置，防止污染仓库根目录与题包目录：任何解析/分析/汇报类产出必须落在
  deliverables/<日期>_<材料名>/ 下，单个题包必须落在其类型目录（OBM/、harbor-16/、harbor-sota/ 及后续新增类型）内的独立子目录，
  只有公用脚本/配置才可放在类型目录根部。Use when working in the wff-task workspace and about to create, move, or write
  any file — especially analysis reports, PDF/document extractions, summaries, comparison docs, ad-hoc scripts, or new
  task packages. Also use when the user says "别污染根目录", "别污染其他题包", "放到该放的地方", "整理目录结构",
  "workspace discipline", or asks where a file should go.
---

# wff-task 工作区落盘纪律

本 skill 约束**文件写到哪里**。在 wff-task 工作区内产生任何文件前，先按本规则确定落点。

## 铁律一：仓库根目录单一制

以下条目**只允许存在一个**，禁止出现同名的第二个（如 `deliverables-2/`、`README2.md`、`skills.bak/`）：

```
README.md  .gitignore  deliverables/  skills/
```

题包类型目录（见铁律二）是**可扩展的**，但每新增一个类型目录都须先经用户同意。

- **禁止**在仓库根目录直接创建任何 `.md`、`.txt`、`.csv`、`.json`、脚本或报告文件。
- 备份目录（`X.backup-*`、`X-2/`）、临时目录（`tmp/`、`new/`）一律**禁止**出现在根目录。

## 铁律二：题包按类型隔离，单包自包含

`OBM/`、`harbor-16/`、`harbor-sota/` 是**题包类型目录**——每个目录代表**一类 skill 的产物集合**。后续还会新增其他类型（例如本轮要解析的 **Windows-Harbor** 作业，应有自己的类型目录）。

规则：

1. **单个题包 = 类型目录下的一个独立子目录**。一题一目录，互不干扰。
2. **类型目录根部只允许放公用内容**，参考 `OBM/`：

   | 可放（公用） | 示例 |
   |---|---|
   | 跨题复用的配置 | `OBM/model.env`、`OBM/feishu-gsb.toml`、`OBM/task-registry.json` |
   | 跨题复用的脚本 | `OBM/tools/` |
   | 公用数据缓存 | `OBM/Benchmark/`、`OBM/upstream/` |
   | 公用记录 | `OBM/feishu-records/`、`OBM/_env-records/` |

3. **题包专属内容只能放进该题包自己的目录内**，禁止上浮到类型目录根部，避免污染其他题包。

   | 归属 | 落点 |
   |---|---|
   | 某题的中间产物、运行记录、baseline | `<类型目录>/work/<题号>/` 或 `<类型目录>/<题包>/` |
   | 某题的成品交付物 | `OBM/output/<题包>/`、`harbor-16/<批次>/`、`harbor-sota/<题包>/` |

4. **新增题包类型时**：先 `mkdir` 类型目录，再在其中按「公用 + 单包目录」两层组织，并在根 `README.md` 登记。

## 铁律三：deliverables/ 是解析材料专用产出区

`deliverables/` 用于存放**对某份材料做解析/分析后的产出**。

**命名规则**：目录名 = `<YYYY-MM-DD>_<材料文件名（去扩展名）>`，**保持材料原名原样**。

```
用户提供的材料：  windwos-第二版.pdf
                ↓
deliverables/     2026-09-29_windwos-第二版/     # 日期 + 材料主名（去扩展名）
```

规则要点：

- **目录名格式**：`<YYYY-MM-DD>_<材料名>`。日期取**产出当日**（用 `date +%F` 获取真实日期，不要凭记忆推算）。
- **保持原名原样**：材料名部分照抄，**包括原始拼写**（如 `windwos` 是原件的拼写，不要"纠正"成 `windows`）。
- **一材料一目录**：同一份材料的所有产出放在同一目录，不拆散。
- 目录内放该材料的解析产物；不再强制产物与材料同名，按内容合理命名即可。

## 落点判定表（速查）

| 产出内容 | 落点 | 示例 |
|---|---|---|
| 解析某份材料的报告 / 清单 / 汇报 | `deliverables/<日期>_<材料名>/` | `deliverables/2026-09-29_windwos-第二版/` |
| 解析所需支撑材料（抽取文本、数据导出） | 同上目录 | `deliverables/2026-09-29_windwos-第二版/抽取.txt` |
| 题包中间产物、运行记录、baseline | `<类型目录>/work/<题号>/` | `OBM/work/2026-09-29-1-pycasbin.../` |
| 成品题包 | `<类型目录>/<题包>/` 或 `OBM/output/<题包>/` | `harbor-sota/COB-L4-002/` |
| 跨题复用配置 / 脚本 / 数据缓存 | 类型目录根部（公用层） | `OBM/tools/`、`OBM/Benchmark/` |
| skill 本体 | `skills/<name>/` | `skills/harbor-16/SKILL.md` |

## 执行流程

1. **写文件前先判类型** —— 对照落点判定表，确定是「解析产出」「题包产物」还是「公用内容」。
2. **确定目标目录** —— 目录不存在则 `mkdir -p` 创建；题包内容先建好单包目录再放入。
3. **只在确定落点后写入** —— 不要先写到根目录/类型目录根部再"稍后整理"。
4. **发现已有污染** —— 立即移动到正确位置；已跟踪的文件用 `git mv` 保留历史。
5. **收尾自检** —— `ls` 复核根目录仍只含 `README.md`/`.gitignore`/`deliverables/`/`skills/` + 已登记的类型目录；`deliverables/` 新增时更新其 `README.md` 索引。

## 反模式（禁止）

| ❌ 错误做法 | ✅ 正确做法 |
|---|---|
| 分析报告写到 `wff-task/报告.md` | 写 `deliverables/<日期>_<材料名>/报告.md` |
| `deliverables/某材料/` 缺日期前缀 | `deliverables/2026-09-29_某材料/` |
| 目录名把材料拼写"纠正" | 保持原件原拼写（`windwos` 不改成 `windows`） |
| 某题脚本/日志丢在 `OBM/` 根部 | 放该题的 `OBM/work/<题号>/` 内 |
| 单个题包与其他题包混在类型目录根部 | 类型目录根部只放公用内容，单包独立子目录 |
| 新建 `analysis/`、`tmp/`、`X-2/` 等根级目录 | 用 `deliverables/` 或已登记的类型目录 |
| 修改后不检查目录 | 每次收尾 `ls` 复核 |

## 与其他 skill 的关系

- `OBM` / `harbor-16` / `harbor-sota` 等管**怎么生产题包**；本 skill 管**产物放哪里**。二者互补，同时生效。
- 若其他 skill 的指令与本 skill 的落盘规则冲突，以**本 skill 的落盘规则为准**。

## 边界

- 用户在**工作区之外**（如桌面、`/tmp`）指定的路径，按其明确要求执行，不受本 skill 约束。
- 用户**显式要求**写到某个非标准位置时，遵循用户指令，但**口头提醒**该位置偏离约定。
- 材料原件本身由用户提供在外部（如桌面）时，`deliverables/` 内放其**副本**或直接放解析产物，不强求复制原件。
