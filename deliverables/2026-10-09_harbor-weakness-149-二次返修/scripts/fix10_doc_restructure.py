# -*- coding: utf-8 -*-
"""fix10 交付文档整理：
 A) 清除 §9 遗留的孤儿表格片段（上次以 '---' 定位被表格分隔行截断所致）
 B) §4 结构图与 §5 清单改为「交付文档在批次根」
 C) §8 改称前轮（fix9）、新增 §9 本轮（fix10）整改段、飞书回写顺延为 §10 并按 fix10 重写
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261011_fix10-149\交付文档.md')
NEW_NAME = 'work_fin-b01_20261011_fix10-149'
t = DOC.read_bytes().decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'
report = []

# ---- A) 删除孤儿片段：从 §9 结尾 '> **口径澄清**...' 之后的残块到日期行之前 ----
i9 = t.find('## 9. 飞书记录回写')
i_orphan = t.find('---|---|', i9)
i_date = t.find('*文档生成：', i9)
if i_orphan > 0 and i_date > i_orphan:
    orphan = t[i_orphan:i_date]
    t = t[:i_orphan] + t[i_date:]
    report.append(f'A) 已删除孤儿片段 {len(orphan)} 字符')
else:
    report.append('A) [WARN] 未定位到孤儿片段')

# ---- B) §4 结构图 ----
old_tree = ('└── FIN3-WKN-149/                               ← 题目目录' + NL +
            '    ├── instruction.md / task.toml / rubrics.json' + NL +
            '    ├── environment/ solution/ tests/           ← 五件套' + NL +
            '    ├── 交付文档.md                              ← 本文件（题目目录内）' + NL +
            '    └── 跑分产物与轨迹/')
new_tree = ('├── 交付文档.md                                  ← 本文件（**批次根**，依质检报告(3) 项6 / rewardkit §8.4）' + NL +
            '└── FIN3-WKN-149/                               ← 题目目录' + NL +
            '    ├── instruction.md / task.toml / rubrics.json' + NL +
            '    ├── environment/ solution/ tests/           ← 五件套' + NL +
            '    └── 跑分产物与轨迹/')
c = t.count(old_tree)
report.append(f'B1) §4 结构图命中 {c} 处')
t = t.replace(old_tree, new_tree, 1)

# §4 引言（项8 说明）加一句本轮移位
old_intro = ('> 依 2026-10-09 质检报告项8：`交付文档.md` 与 `跑分产物与轨迹/` **归档于题目目录内**，'
             '与五件套同级；四执行体保持独立目录。')
new_intro = ('> 依 2026-10-09 质检报告项8：`跑分产物与轨迹/` **归档于题目目录内**，四执行体保持独立目录；'
             '`交付文档.md` 依 **2026-10-11 质检报告(3) 项6 / rewardkit §8.4** 置于**批次根**。')
c = t.count(old_intro)
report.append(f'B2) §4 引言命中 {c} 处')
t = t.replace(old_intro, new_intro, 1)

# ---- §5 清单路径 ----
old5 = ('| 1 | 交付文档（本文件） | `' + NEW_NAME + '/FIN3-WKN-149/交付文档.md` |')
new5 = ('| 1 | 交付文档（本文件） | `' + NEW_NAME + '/交付文档.md`（**批次根**） |')
c = t.count(old5)
report.append(f'B3) §5 清单命中 {c} 处')
t = t.replace(old5, new5, 1)

# ---- C) §8 改称前轮、新增 §9 本轮、飞书回写顺延 §10 ----
old_h8 = '## 8. 本轮（2026-10-11 金标三处计算修正）整改记录'
new_h8 = '## 8. 前轮（2026-10-11，fix9：金标三处计算修正）整改记录'
c = t.count(old_h8)
report.append(f'C1) §8 标题命中 {c} 处')
t = t.replace(old_h8, new_h8, 1)

fix10_sec = f'''## 9. 本轮（2026-10-11，fix10：Oracle 同源产物补跑 + 根交付说明移位）整改记录

甲方于 2026-10-11 出具**质检报告(3)**（结论：待改，类型「重跑/补全 job」），指出 2 项【待改】。本轮逐条闭环，**三模型 agent 不重跑**（报告明示"现有 agent 作答可保留"）。

| # | 质检问题 | 处置 | 闭环证据 |
|---|---|---|---|
| **项3** | Oracle 归档**混入旧产物**：`oracle/output` 的脚本与备忘录与修后新 gold 相同，但**五张 PNG 全部仍与 fix8 旧 Oracle 图同字节**（图4-a 推荐约 5.05%、方案B 约 7.03%，图4-c 标题仍"最小马氏距离 15.19"），而新 gold 对应 5.56% / 7.46% / 18.38；R28/R31 的理由却按新值书写，不能由旧图支持 | **定位根因**：fix9 轮同步 WSL 任务目录时**只同步了 `reproduce.py` / 备忘录 / `rubrics.toml`，漏同步 5 张重生成的 PNG**；而 `solution/solve.sh` 为 `cp -R /solution/golden_output/. /app/output/`，故 Oracle 运行时取到的是**旧图**，进而归档进 `oracle/output`。**修复**：① 将修后 5 张新图补同步至 WSL 任务目录的 `solution/golden_output/` 与 `tests/__golden_output/`（两个目录 7 件套**逐字节校验一致**）；② **重跑 Oracle**（新试次），取得**真实同源完整七件套**；③ 重判 Oracle 全部 36 条判据 | ① 五图哈希由 `43ccceb6…/7c9574ca…/f6cac8bc…/e5b293c8…/fdc790d6…`（fix8 旧图）变为 `4260f3cd…/6875a495…/94526dc9…/f4858537…/9a869d3b…`（修后新图），与 `solution/golden_output` **逐字节一致**；② Oracle 新试次 `FIN3-WKN-149__('{"__PLACEHOLDER__"}')`（见 §3.1 实测试次号）；③ 新 Oracle 归档产物的脚本/备忘录/五图**同源**，图4-a 为 10.16/7.46/6.96/5.56/9.26、图4-c 马氏距离 **18.38**；④ 重判后 R28/R31 的通过理由与**新图内容一致** |
| **项6** | **根交付说明位置**：`交付文档.md` 仍在题目目录，批次根未有该文档（违反 rewardkit §8.4 / 交付规范 §4 第 17 项自检） | 将现有 `交付文档.md` **移至批次根**，并**保留环境变量说明**（§2 完整 8 项 `[verifier.env]` 表原样保留）；不改变评分语义 | ① 批次包结构：`{NEW_NAME}/交付文档.md`（根）+ `{NEW_NAME}/FIN3-WKN-149/{{五件套, 跑分产物与轨迹/}}`；② 本文档 §4 结构图与 §5 清单同步更新；③ `check_package_permissions.py` 的「批次根目录有 交付文档.md」校验通过 |

> **未改动项（报告判【正确】，本轮维持）**：项1 基线与 metadata / 项2 上轮三处金标修复（国债 bp÷10000、境内权益逐项加权、SPX 反算补 +1/−1；S4 国债 0.0172%、推荐损益 −5.564754%、方案B −7.4557%、马氏 18.38）、项4 三模型证据与签名归一化（GPT 120.25/204=0.5894607843、Opus 132.5/204=0.6495098039、Qwen 173.5/204=0.8504901961，均值 0.6964869281）、项5 业务与题面、项7 甲方静态与最终 ZIP（F06 仅命中正式跑分 reward/details，不删除）。

### 9.1 fix10 交付文档位置说明（对照报告项6）

本包依 **rewardkit §8.4** 与《交付规范》§4 采用如下层级：

```
{NEW_NAME}/                       ← 批次目录（zip 根）
├── 交付文档.md                    ← 本文件（环境变量配置说明等，必交，放批次根）
└── FIN3-WKN-149/                  ← 题目目录
    ├── instruction.md / task.toml / rubrics.json
    ├── environment/ solution/ tests/
    └── 跑分产物与轨迹/            ← 四执行体证据（依 10-09 报告项8 归档于题目目录内）
```

---

'''

old_h9 = '## 9. 飞书记录回写'
c = t.count(old_h9)
report.append(f'C2) 原 §9 标题命中 {c} 处')
if c == 1:
    t = t.replace(old_h9, fix10_sec + '## 10. 飞书记录回写', 1)

# ---- D) 飞书回写段按 fix10 重写 ----
i10 = t.find('## 10. 飞书记录回写')
i_after = t.find('*文档生成：', i10)
new_s10 = f'''## 10. 飞书记录回写

| 项 | 值 |
|---|---|
| Base / Table | `QpzNb4fXSamfX6sLloBcPfHNnug` / `tblPNrBtjFfwOowN` |
| 记录 ID | `rec28himvkSA77`（FIN3-WKN-149） |

**本轮（fix10）回写内容**（均 `rc=0`，已 `+record-list` 复核终态）：

| 字段（`field_id`） | 类型 | 动作 | 终态 |
|---|---|---|---|
| 交付物 `fld8TMUhqI` | attachment | 先删旧 fix9 包、再传本轮 fix10 包 | 仅 `{NEW_NAME}.zip`（单一附件） |
| 题目附件 `fldf8Ymaw2` | attachment | 同名前删后传 | `FIN3-WKN-149_task.zip`（本轮**内容未变**，重传保持与包内一致） |
| 标准答案附件 `fld2TmGhqt` | attachment | 同名前删后传 | `FIN3-WKN-149_answer.zip`（本轮**内容未变**） |
| 题目难度 `fldYA4iRaD` | select | 维持 **A1**（未改） | `A1` |
| 考点信息（rubrics）`fldqj9Zstn` | text | 维持 fix9 已同步的修后数值（本轮金标数值未再变化） | 与包内金标同源一致 |
| 质检报告 `fld92VdQU6` | attachment | 甲方已替换为 `序号149_质检报告 (3).md`，未改动 | 本轮质检依据 |
| 状态 `fldKFzG0cA` | select | 不动（标注人不可写） | 仍为「待返修」，由质检方复检后流转 |

> **口径澄清**：「参考答案」为文本字段 `fld2LBu2Ns`；`fld2TmGhqt` 实为「标准答案附件信息」（承载 answer.zip），二者不可混用。

---

'''
if i10 > 0 and i_after > i10:
    t = t[:i10] + new_s10 + t[i_after:]
    report.append('D) §10 飞书回写段已按 fix10 重写')
else:
    report.append('D) [WARN] 未定位 §10')

# 日期行
for ln in t.split(NL):
    if ln.startswith('*文档生成：'):
        t = t.replace(ln,
                      '*文档生成：2026-10-09；fix8 跑分与归档：2026-10-10；fix9 金标三处修正与重跑：2026-10-11；'
                      f'**fix10 Oracle 同源产物补跑与根交付说明移位：2026-10-11**（FIN3-WKN-149 四次返修重交版 '
                      f'**1.0.8**，批次 `{NEW_NAME}`）；验证环境：WSL Ubuntu + Docker Engine 29.x.*', 1)
        break

DOC.write_bytes(t.encode('utf-8'))
print('\n'.join(report))
print(f'\n[OK] 文档 {len(t.encode("utf-8")):,} B')
print(f'[检查] 章节: {[l for l in t.split(NL) if l.startswith("## ")]}')
print(f'[检查] 残留孤儿 "---|---|" 次数: {t.count("---|---|")}（应为 1，即正文表格分隔）')
