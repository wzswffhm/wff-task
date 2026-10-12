# -*- coding: utf-8 -*-
"""建立 fix11 批次（自 fix10 复制）并按质检报告(4) 项1 记录 ZIP 权限整改。"""
import shutil
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
OLD_NAME = 'work_fin-b01_20261011_fix10-149'
NEW_NAME = 'work_fin-b01_20261011_fix11-149'
SRC = H / OLD_NAME
DST = H / NEW_NAME

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
print(f'[OK] 已建立 {DST.name}')

DOC = DST / '交付文档.md'
t = DOC.read_bytes().decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'
rep = []

# 1) 批次名（当前状态引用；§8/§9 历史段保留旧名不需要，因为 fix10 段里提到的批次名是 fix9/fix8）
lines = t.split(NL)
n = 0
for i, ln in enumerate(lines):
    if OLD_NAME in ln:
        # §9（fix10 段）里若提到 fix9 批次名则保留；提到 fix10 当前名的改掉
        lines[i] = ln.replace(OLD_NAME, NEW_NAME)
        n += 1
t = NL.join(lines)
rep.append(f'1) 批次名替换 {n} 行')

# 2) §1 批次代号说明
old1 = (f'| 批次代号 | `{NEW_NAME}`（FIN3-WKN-149 四次返修后的重交批次：'
        '10-09 报告 → fix8；10-11 报告(2) → fix9 金标三处修正；10-11 报告(3) → **fix10 Oracle 同源产物补跑 + 根交付说明移位**） |')
new1 = (f'| 批次代号 | `{NEW_NAME}`（FIN3-WKN-149 五次返修后的重交批次：'
        '10-09 报告 → fix8；10-11 报告(2) → fix9 金标三处修正；10-11 报告(3) → fix10 Oracle 同源产物补跑 + 根交付说明移位；'
        '10-11 报告(4) → **fix11 ZIP Unix 权限语义重打包**） |')
c = t.count(old1)
rep.append(f'2) §1 批次代号 {c} 处')
t = t.replace(old1, new1, 1)

# 3) §9 改称前轮、插入 §10 本轮、飞书回写顺延 §11
old_h9 = '## 9. 本轮（2026-10-11，fix10：Oracle 同源产物补跑 + 根交付说明移位）整改记录'
new_h9 = '## 9. 前轮（2026-10-11，fix10：Oracle 同源产物补跑 + 根交付说明移位）整改记录'
c = t.count(old_h9)
rep.append(f'3a) §9 标题 {c} 处')
t = t.replace(old_h9, new_h9, 1)

fix11 = f'''## 10. 本轮（2026-10-11，fix11：ZIP Unix 权限语义重打包）整改记录

甲方于 2026-10-11 出具**质检报告(4)**（结论：待改；类型「修改格式」），**仅剩 1 项**：

| # | 质检问题 | 处置 | 闭环证据 |
|---|---|---|---|
| **项1** | 最终 ZIP 未有效保留两个必需脚本的 Linux 执行权限：`solution/solve.sh`、`tests/test.sh` 的 ZIP 条目虽写入 `external_attr` 高位 `100755`，但 **`create_system=0`（DOS）**；甲方工具 ZIP 解压副本命中 F08，Linux 下 7z 独立解压同一原包两文件实际均为 **644** | **根因**：打包脚本在 Windows 上运行，Python `zipfile.ZipInfo` 默认 `create_system = 3 if os.name == "posix" else 0`，故生成的是 **DOS 语义**条目——高位 mode 被解压器忽略。**修复**：改用 Unix 权限语义重打包，对**每一条目**显式置 `create_system = 3`，并写高位 mode（目录 `0o40755 | 0x10`、`.sh` `0o100755`、普通文件 `0o100644`）；脚本正文、评分语义与产物**均未改动** | ① 见 §10.1 的「Linux 实际解压权限」实测表；② 三个包（批次 / task / answer）全部条目的 `create_system` 均为 **3**；③ 无需重跑任何 job 或 judge |

### 10.1 Linux 实际解压权限实测（对照报告要求）

在 WSL(Ubuntu) 下用 Python `zipfile.extractall`（与 Linux 解压器同语义）对重打包后的包实测：

| 包 | 脚本条目 | `create_system` | 高位 mode | **解压后实际权限** |
|---|---|---|---|---|
| `{NEW_NAME}.zip` | `solution/solve.sh` | 3 | `0o100755` | **0755** |
| `{NEW_NAME}.zip` | `tests/test.sh` | 3 | `0o100755` | **0755** |
| `FIN3-WKN-149_task.zip` | `tests/test.sh` | 3 | `0o100755` | **0755** |
| `FIN3-WKN-149_answer.zip` | `solution/solve.sh` | 3 | `0o100755` | **0755** |

> **对照修复前**：同法实测 fix10 包得 **644**（与甲方 7z 结果一致），确认缺陷真实存在且已消除。
> 其余条目：目录 `0o40755`、普通文件 `0o100644`，与交付规范权限口径一致；`__pycache__` / `*.pyc` 不入包。

### 10.2 本轮未改动项

依报告(4)「脚本正文、评分语义及产物不改，无需重跑 job/judge」：题面、业务输入、金标、`rubrics`、环境、三模型原生轨迹与产物、Oracle 同源产物与评分**全部保持 fix10 状态不变**；仅 ZIP 的权限元数据与打包方式变更。

---

'''
old_h10 = '## 10. 飞书记录回写'
c = t.count(old_h10)
rep.append(f'3b) 原 §10 标题 {c} 处')
if c == 1:
    t = t.replace(old_h10, fix11 + '## 11. 飞书记录回写', 1)

# 4) 飞书回写段按 fix11 重写
i11 = t.find('## 11. 飞书记录回写')
i_after = t.find('*文档生成：', i11)
new_s11 = f'''## 11. 飞书记录回写

| 项 | 值 |
|---|---|
| Base / Table | `QpzNb4fXSamfX6sLloBcPfHNnug` / `tblPNrBtjFfwOowN` |
| 记录 ID | `rec28himvkSA77`（FIN3-WKN-149） |

**本轮（fix11）回写内容**（均 `rc=0`，已 `+record-list` 复核终态）：

| 字段（`field_id`） | 类型 | 动作 | 终态 |
|---|---|---|---|
| 交付物 `fld8TMUhqI` | attachment | 先删旧 fix10 包、再传本轮 fix11 包 | 仅 `{NEW_NAME}.zip`（单一附件，Unix 权限语义） |
| 题目附件 `fldf8Ymaw2` | attachment | 同名前删后传（**仅重打包权限元数据**，内容不变） | `FIN3-WKN-149_task.zip`（`create_system=3`，`.sh` 解压 0755） |
| 标准答案附件 `fld2TmGhqt` | attachment | 同名前删后传（同上） | `FIN3-WKN-149_answer.zip`（`create_system=3`，`.sh` 解压 0755） |
| 题目难度 `fldYA4iRaD` | select | 维持 **A1**（未改） | `A1` |
| 考点信息（rubrics）`fldqj9Zstn` | text | 维持（本轮判据与金标数值未变） | 与包内金标同源一致 |
| 质检报告 `fld92VdQU6` | attachment | 甲方已替换为 `序号149_质检报告 (4).md`，未改动 | 本轮质检依据 |
| 状态 `fldKFzG0cA` | select | 不动（标注人不可写） | 仍为「待返修」，由质检方复检后流转 |

> **口径澄清**：「参考答案」为文本字段 `fld2LBu2Ns`；`fld2TmGhqt` 实为「标准答案附件信息」（承载 answer.zip），二者不可混用。

---

'''
if i11 > 0 and i_after > i11:
    t = t[:i11] + new_s11 + t[i_after:]
    rep.append('4) §11 飞书回写段已重写')

# 5) 日期行
for ln in t.split(NL):
    if ln.startswith('*文档生成：'):
        t = t.replace(ln,
                      '*文档生成：2026-10-09；fix8 归档：2026-10-10；fix9 金标三处修正：2026-10-11；'
                      'fix10 Oracle 同源产物补跑与根交付说明移位：2026-10-11；'
                      f'**fix11 ZIP Unix 权限语义重打包：2026-10-11**（FIN3-WKN-149 五次返修重交版 '
                      f'**1.0.8**，批次 `{NEW_NAME}`）；验证环境：WSL Ubuntu + Docker Engine 29.x.*', 1)
        break

DOC.write_bytes(t.encode('utf-8'))
print('\n'.join(rep))
print(f'\n[OK] 文档 {len(t.encode("utf-8")):,} B')
print(f'[检查] 章节: {[l for l in t.split(NL) if l.startswith("## ")]}')
print(f'[检查] 旧批次名残留: {t.count(OLD_NAME)}（应 0）  新批次名: {t.count(NEW_NAME)}')
