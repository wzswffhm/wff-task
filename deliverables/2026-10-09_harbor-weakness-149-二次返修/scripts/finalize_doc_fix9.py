# -*- coding: utf-8 -*-
"""fix9 交付文档收尾：
1) 当前轮批次名 fix8 -> fix9（保留 §7 历史轮引用）
2) §4.1 第1条改为本轮「oracle 新跑 + 三模型重判官」口径
3) §9 飞书回写段重写为 fix9 本轮内容
4) summary.json 的 batch 字段同步
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
BATCH = H / 'work_fin-b01_20261011_fix9-149'
DOC = BATCH / 'FIN3-WKN-149' / '交付文档.md'
OLD_NAME = 'work_fin-b01_20261009_fix8-149'
NEW_NAME = 'work_fin-b01_20261011_fix9-149'

t = DOC.read_bytes().decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'
lines = t.split(NL)

# ---- 1) 当前轮批次名替换（跳过 §7 历史轮行）----
SKIP_MARK = '批次包结构改为'          # §7 项8 历史行
n_ren = 0
for i, ln in enumerate(lines):
    if OLD_NAME in ln and SKIP_MARK not in ln:
        lines[i] = ln.replace(OLD_NAME, NEW_NAME)
        n_ren += ln.count(OLD_NAME)
t = NL.join(lines)
print(f'[1] 批次名替换 {n_ren} 处（保留历史轮引用 1 处）')

# ---- 2) §4.1 第1条 ----
old41 = ('1. **四执行体统一 `output/`**：`oracle` / `gpt-5.6-sol` / `claude-opus-4-8` / '
         '`qwen3.8-max-0902` 均以 `output/` 承载交付物；四者均归档**本轮 fix8 全量重跑**的产物与轨迹。')
new41 = ('1. **四执行体统一 `output/`**：`oracle` / `gpt-5.6-sol` / `claude-opus-4-8` / '
         '`qwen3.8-max-0902` 均以 `output/` 承载交付物。本轮（fix9）为**金标三处计算修正轮**：'
         '`oracle` 归档**新跑试次**（执行修复后金标，G4=1.000000）的产物与轨迹；三模型按甲方'
         '「返修类型=重跑判官」复用 **fix8 agent 原生产物**、以修复后判据**重新判分**，'
         '产物与轨迹仍为 fix8 采用轮（agent 输入与规则本轮未变）。')
if old41 in t:
    t = t.replace(old41, new41, 1)
    print('[2] §4.1 第1条已更新')
else:
    print('[2][WARN] §4.1 第1条未命中')

# ---- 3) §9 飞书回写段重写 ----
i9 = t.find('## 9. 飞书记录回写')
i_end = t.find('---', i9)
if i9 < 0:
    print('[3][ERR] 未找到 §9')
    sys.exit(1)
new_s9 = f'''## 9. 飞书记录回写

| 项 | 值 |
|---|---|
| Base / Table | `QpzNb4fXSamfX6sLloBcPfHNnug` / `tblPNrBtjFfwOowN` |
| 记录 ID | `rec28himvkSA77`（FIN3-WKN-149） |

**本轮（fix9）回写内容**（均 `rc=0`，已 `+record-list` 复核终态）：

| 字段（`field_id`） | 类型 | 动作 | 终态 |
|---|---|---|---|
| 题目附件 `fldf8Ymaw2` | attachment | 同名前删后传 | `FIN3-WKN-149_task.zip`（含修正后 `reproduce.py`、重建金标与 `[scoring]` 判据） |
| 标准答案附件 `fld2TmGhqt` | attachment | 同名前删后传 | `FIN3-WKN-149_answer.zip`（含重建后金标 7 件套） |
| 交付物 `fld8TMUhqI` | attachment | 先删旧 fix8 包、再传本轮 fix9 包 | 仅 `{NEW_NAME}.zip`（单一附件） |
| 题目难度 `fldYA4iRaD` | select | 维持 **A1**（本轮实测均分 0.696487 仍 ∈ A1，未改） | `A1` |
| 考点信息（rubrics）`fldqj9Zstn` | text | **按金标修正同步数值**：考点8/9/10/11/14 的压力损失、超限幅度、反向压力情景与马氏距离全部更新（如方案A 最大损失 9.902%→**10.157%**、推荐方案 5.045%→**5.565%**、推荐方案马氏距离 15.19→**18.38**、委员会冲击 50.77→**52.08**） | 与包内修复后金标**同源一致**（全文 5,787 字，`9.902`/`7.030`/`5.045`/`15.19`/`50.77` 旧值残留均为 0） |
| 质检报告 `fld92VdQU6` | attachment | 甲方已替换为 `序号149_质检报告 (2).md`，未改动 | 本轮质检依据 |
| 状态 `fldKFzG0cA` | select | 不动（标注人不可写） | 仍为「待返修」，由质检方复检后流转 |

> **口径澄清**：「参考答案」为文本字段 `fld2LBu2Ns`；`fld2TmGhqt` 实为「标准答案附件信息」（承载 answer.zip），二者不可混用。

'''
t = t[:i9] + new_s9 + t[i_end:]
print('[3] §9 飞书回写段已重写')

# 日期行
for i, ln in enumerate(t.split(NL)):
    if ln.startswith('*文档生成：'):
        newl = ('*文档生成：2026-10-09；fix8 跑分与归档：2026-10-10；'
                '**fix9 金标三处修正与重跑：2026-10-11**（FIN3-WKN-149 三次返修重交版 **1.0.8**，'
                f'批次 `{NEW_NAME}`）；验证环境：WSL Ubuntu + Docker Engine 29.x.*')
        t = t.replace(ln, newl, 1)
        break

DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 文档 {len(t.encode("utf-8")):,} B')
print(f'[检查] 旧批次名残留: {t.count(OLD_NAME)}（应为 1，即 §7 历史行）')
print(f'[检查] 新批次名出现: {t.count(NEW_NAME)}')

# ---- 4) summary.json batch 字段 ----
sj = BATCH / 'FIN3-WKN-149' / '跑分产物与轨迹' / 'summary.json'
d = json.loads(sj.read_text(encoding='utf-8'))
d['batch'] = NEW_NAME
d['task_version'] = '1.0.8'
sj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[4] summary.json batch -> {d["batch"]}  均分={d["model_mean"]}  gate={d["gate_pass"]}')
