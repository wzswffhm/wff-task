#!/usr/bin/env python3
"""RL0-1 判据自检：rubrics.json ↔ tests/rubrics.toml 一致性 + 规范门禁。

用法: python validate_rubrics.py <task-dir> [<task-dir> ...]

覆盖可机械判定的部分：条数与领域下限、维度名、weight 取值与分布、+10 条数、
内容质量占比、负分集合一致性、likert 标度与锚点一致性（含历史上出现过的
levels 相对 description 整体错位一档）、禁字符与换行。
题目真实性、trigger 是否真能诱发 weakness、参考答案是否专业正确仍需人工判断。

本地增量（2026-10-01，与上游 verbatim 版的差异）：
  1. rubrics.json 顶层支持三种形态：list / {"items": [...]} / {"rubrics": [...]}
     （上游只认 items，遇到 {"rubrics": ...} 直接 KeyError 崩掉，整题被判阻断——
      真实案例：FIN1-skill-DEP-003）。
  2. 「领域相关结构下限」按 domain 分流：条数下限、11 个固定维度名、负分条数与档位下限
     目前只有**法律领域**的规范依据（简单 25 / 中等 30 / 复杂 35）。其他领域（金融、代码、
     skill 类）下限未下发，改为 NOTE 不判 FAIL。真实案例：FIN1-skill-DEP-003 只有 8 条
     判据、1 条负分，甲方人检判「区分度/完整性 ✅ 合格」；上游脚本会报「条数 8 >= A3 下限 35」
     「负分条目 1 条 >= 2」误报阻断。
"""
import json
import os
import re
import sys

VALID_DIM = ['指令遵循', '内容质量-结论正确性', '内容质量-数值与计算准确性',
             '内容质量-专业规范', '内容质量-分析与论证质量', '内容质量-事实忠实性',
             '结构与组织', '操作与交付安全', '安全合规', '超预期贡献', '视觉美感']
LEVEL_ORDER = ['1', '0.75', '0.5', '0.25', '0']
TAIL = re.compile(r'按[^。；]{0,12}评分：\s*(.*)$', re.S)


def task_domain(task_dir):
    toml = open(os.path.join(task_dir, 'task.toml'), encoding='utf-8').read()
    m = re.search(r'(?m)^domain\s*=\s*"([^"]+)"', toml)
    return m.group(1) if m else ''


def domain_floor(task_dir, items):
    """条数下限只在**法律领域**有规范依据；其他领域的下限未下发，返回 None。

    返回 (floor 或 None, 难度档, domain)。
    """
    toml = open(os.path.join(task_dir, 'task.toml'), encoding='utf-8').read()
    diff = re.search(r'difficulty\s*=\s*"(A\d)"', toml)
    diff = diff.group(1) if diff else 'A2'
    dom = task_domain(task_dir)
    if '法律' not in dom and dom:
        return None, diff, dom
    return {'A1': 25, 'A2': 30, 'A3': 35}[diff], diff, dom or '法律(未声明)'


def load_items(task_dir):
    """rubrics.json 顶层支持 list / {"items"} / {"rubrics"} / {"criteria"}。"""
    raw = json.load(open(os.path.join(task_dir, 'rubrics.json'), encoding='utf-8'))
    if isinstance(raw, list):
        return raw, None
    for key in ('items', 'rubrics', 'criteria'):
        if isinstance(raw.get(key), list):
            return raw[key], raw
    for value in raw.values():          # 兜底：取第一个列表值
        if isinstance(value, list):
            return value, raw
    raise SystemExit('rubrics.json 顶层既不是列表，也找不到包含条目的列表字段')


def parse_anchors(text):
    out = {}
    for part in re.split(r'[；;]', text):
        m = re.match(r'\s*(1|0\.75|0\.5|0\.25|0)\s*=\s*(.*)', part.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().rstrip('。')
    return out


def check(task_dir):
    bad = []

    def chk(cond, msg):
        print(('  OK   ' if cond else '  FAIL ') + msg)
        if not cond:
            bad.append(msg)

    items, raw = load_items(task_dir)
    smax_json = (raw.get('metadata', {}).get('scoring', {}).get('s_max')
                 if isinstance(raw, dict) else None)
    tpath = os.path.join(task_dir, 'tests', 'rubrics.toml')
    toml = open(tpath, encoding='utf-8').read() if os.path.isfile(tpath) else ''
    blocks = re.findall(r'\[\[criterion\]\](.*?)(?=\n\[\[criterion\]\]|\Z)', toml, re.S)

    floor, diff, dom = domain_floor(task_dir, items)
    pos = sum(float(i['weight']) for i in items if float(i['weight']) > 0)
    neg = sum(-float(i['weight']) for i in items if float(i['weight']) < 0)
    tpos = sum(float(re.search(r'weight = ([0-9.]+)', b).group(1)) for b in blocks
               if 'negate = true' not in b)
    neg_ids = {i['id'] for i in items if float(i['weight']) < 0}
    tneg = {re.search(r'id = "([^"]+)"', b).group(1) for b in blocks
            if 'negate = true' in b}

    chk(len(items) == len(blocks), f'json 条数 {len(items)} == toml 条数 {len(blocks)}')
    if floor is None:
        # 本地增量：非法律领域的条数下限未下发，不判 FAIL，交人工/甲方确认
        print(f'  NOTE 领域「{dom}」的条数下限未下发，跳过下限判定'
              f'（现 {len(items)} 条，难度档 {diff}）——法律领域才是 25/30/35；'
              f'请回甲方确认该领域下限')
    else:
        chk(len(items) >= floor, f'条数 {len(items)} >= {diff} 下限 {floor}（{dom}）')
    off_dim = sorted({i['dimension'] for i in items if i['dimension'] not in VALID_DIM})
    if off_dim and floor is None:
        # 本地增量：维度名清单同属领域相关口径，非法律领域只提示
        print(f'  NOTE 清单外的 dimension（{dom} 领域的维度表未下发，请回甲方确认）：'
              + '、'.join(off_dim))
    else:
        chk(all(i['dimension'] in VALID_DIM for i in items),
            '全部 dimension 在 11 个固定清单内')
    chk({float(i['weight']) for i in items} <= {3, 7, 10, -3, -7, -10}, 'weight 取值合法')
    chk(sum(1 for i in items if float(i['weight']) == 10) >= 2, '+10 条目 >= 2 条')
    q = sum(float(i['weight']) for i in items
            if float(i['weight']) > 0 and i['dimension'].startswith('内容质量'))
    chk(q / pos >= 0.3, f'内容质量正分占比 {q / pos:.0%} >= 30%')
    if floor is None:
        # 本地增量：非法律领域的负分条数/档位下限未下发（FIN1-skill-DEP-003 仅 1 条负分，
        # 甲方人检仍判「区分度 ✅ 合格」）
        print(f'  NOTE 非法律领域的负分条数/档位下限未下发，跳过判定'
              f'（现负分 {len(neg_ids)} 条，档位 '
              f'{sorted({abs(float(i["weight"])) for i in items if float(i["weight"]) < 0})}）'
              f'；请回甲方确认')
    else:
        chk(len(neg_ids) >= 2, f'负分条目 {len(neg_ids)} 条 >= 2')
        chk(len({abs(float(i['weight'])) for i in items if float(i['weight']) < 0}) >= 2,
            '负分条目至少两档（如 -3 / -7）')
    chk(tneg == neg_ids, f'toml negate 集合与 json 负分集合一致（{len(tneg)} 条）')
    chk(tpos == pos, f'toml 正分池 {tpos:.0f} == json 正分池 {pos:.0f}')
    if smax_json is not None:
        chk(smax_json == pos, f'metadata.scoring.s_max {smax_json} == 正分池 {pos:.0f}')
    chk(not re.search(r'type = "(?!binary|likert)', toml), 'type 只出现 binary / likert')
    chk(all('points = 5' in b for b in blocks if 'type = "likert"' in b),
        'likert 条目均显式 points = 5')
    chk(not re.search(r'0\.75=|0\.25=', toml), 'toml 中无旧 0–1 标度残留')
    chk('Deliverables to inspect' in toml and 'Deliverables to inspect: ``' not in toml,
        '每条 description 带交付物清单且无空清单')
    chk('。。' not in toml and '。；' not in toml, '无重复标点')
    chk(not any(c in toml for c in ('\u00a0', '\u3000')), '无 NBSP / 全角空格')
    chk('\r' not in toml, 'LF 换行')
    chk(len(toml.encode('utf-8')) < 100 * 1024,
        f'prompt+criteria 体量 {len(toml.encode("utf-8")) / 1024:.0f} KB < 100 KB')

    # levels 与 description 档位段一致性（历史坑：整体错位一档）
    mismatch = []
    for it in items:
        if str(it['type']).lower() != 'gradient':
            continue
        m = TAIL.search(it['description'])
        lv = it.get('levels') or {}
        if not m or not re.match(r'\s*1\s*=', m.group(1)):
            if not lv:
                mismatch.append(f'{it["id"]} 缺 levels')
            continue
        want = parse_anchors(m.group(1))
        if want and {k: v for k, v in lv.items() if k in want} != want:
            mismatch.append(f'{it["id"]} levels 与描述档位段不一致')
    chk(not mismatch, f'likert 锚点一致性 {mismatch or "OK"}')

    print(f'  —— 正分池 {pos:.0f}  负分池 {neg:.0f}  条目 {len(items)}  档位 {diff}')
    return bad


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if not args:
        raise SystemExit(__doc__)
    total = 0
    for d in args:
        d = d.rstrip('/').rstrip('\\')
        print('===== ' + os.path.basename(d))
        total += len(check(d))
    print('\nFAIL 合计:', total)
    sys.exit(1 if total else 0)
