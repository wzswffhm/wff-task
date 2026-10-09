# -*- coding: utf-8 -*-
"""补齐 rubrics.json 的 metadata.scoring（原文件 indent=1，上一步脚本按 2 空格未命中）。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149\rubrics.json')

OLD = (' "scoring": {\n'
       '   "s_max": 204.0,\n'
       '   "pooling": "reward = clip((sum(pos_w*v) - sum(neg_w*(1-v))) / s_max, 0, 1)"\n'
       '  },')

NEW = (' "scoring": {\n'
       '   "s_max": 204.0,\n'
       '   "v_definition": "v 为归一化后的**正向满足度**：1 = 完全满足该条要求，0 = 完全不满足。",\n'
       '   "positive_entries": "正向条目 v = (judge_raw − 1) / 4，judge_raw ∈ {1,2,3,4,5}；'
       'levels 比例键与 judge_raw 按 raw = 1 + 4 × key 一一对应（key 1 ↔ raw 5 = 完全满足）。",\n'
       '   "negate_entries": "负向条目（negate）的 levels 键与判官锚点描述的是**违规程度**而非满足度：'
       'key 1 ↔ judge_raw 5 = 违规完全成立，key 0 ↔ judge_raw 1 = 完全无违规。'
       '计分前先由 rewardkit 翻转 v = 1 − (judge_raw − 1) / 4，再代入 pooling；'
       '因此违规越重 → judge_raw 越大 → v 越小 → 扣分 neg_w × (1 − v) 越大：'
       'judge_raw 1（无违规）扣 0，judge_raw 5（违规完全成立）扣满 neg_w。换算关系即 v = 1 − 违规程度。",\n'
       '   "pooling": "reward = clip((sum(pos_w*v) - sum(neg_w*(1-v))) / s_max, 0, 1)",\n'
       '   "pooling_note": "公式中的 v 一律为翻转后的正向满足度；negate 条目的 levels 键先按 negate_entries 的换算关系翻转再代入。"\n'
       '  },')

data = P.read_bytes()
txt = data.decode('utf-8')
o = OLD.replace('\n', '\r\n')
n = NEW.replace('\n', '\r\n')
cnt = txt.count(o)
print('命中次数:', cnt)
if cnt != 1:
    print(repr(txt[txt.find('"scoring"'):txt.find('"scoring"') + 200]))
    sys.exit(2)
P.write_bytes(txt.replace(o, n).encode('utf-8'))
print('已写入')
