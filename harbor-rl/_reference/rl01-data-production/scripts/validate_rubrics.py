#!/usr/bin/env python3
"""RL0-1 判据自检：rubrics.json ↔ tests/rubrics.toml 一致性 + 规范门禁。

用法: python validate_rubrics.py <task-dir> [<task-dir> ...]

覆盖可机械判定的部分：条数与领域下限、维度名、weight 取值与分布、+10 条数、
内容质量占比、负分集合一致性、likert 标度与锚点一致性（含历史上出现过的
levels 相对 description 整体错位一档）、禁字符与换行。
题目真实性、trigger 是否真能诱发 weakness、参考答案是否专业正确仍需人工判断。
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


def domain_floor(task_dir, items):
    """法律领域有明确的条数下限（简单 25 / 中等 30 / 复杂 35），其他领域按难度取同名下限。"""
    toml = open(os.path.join(task_dir, 'task.toml'), encoding='utf-8').read()
    diff = re.search(r'difficulty\s*=\s*"(A\d)"', toml)
    diff = diff.group(1) if diff else 'A2'
    return {'A1': 25, 'A2': 30, 'A3': 35}[diff], diff


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

    raw = json.load(open(os.path.join(task_dir, 'rubrics.json'), encoding='utf-8'))
    items = raw['items'] if isinstance(raw, dict) else raw
    smax_json = (raw.get('metadata', {}).get('scoring', {}).get('s_max')
                 if isinstance(raw, dict) else None)
    tpath = os.path.join(task_dir, 'tests', 'rubrics.toml')
    toml = open(tpath, encoding='utf-8').read() if os.path.isfile(tpath) else ''
    blocks = re.findall(r'\[\[criterion\]\](.*?)(?=\n\[\[criterion\]\]|\Z)', toml, re.S)

    floor, diff = domain_floor(task_dir, items)
    pos = sum(float(i['weight']) for i in items if float(i['weight']) > 0)
    neg = sum(-float(i['weight']) for i in items if float(i['weight']) < 0)
    tpos = sum(float(re.search(r'weight = ([0-9.]+)', b).group(1)) for b in blocks
               if 'negate = true' not in b)
    neg_ids = {i['id'] for i in items if float(i['weight']) < 0}
    tneg = {re.search(r'id = "([^"]+)"', b).group(1) for b in blocks
            if 'negate = true' in b}

    chk(len(items) == len(blocks), f'json 条数 {len(items)} == toml 条数 {len(blocks)}')
    chk(len(items) >= floor, f'条数 {len(items)} >= {diff} 下限 {floor}')
    chk(all(i['dimension'] in VALID_DIM for i in items),
        '全部 dimension 在 11 个固定清单内')
    chk({float(i['weight']) for i in items} <= {3, 7, 10, -3, -7, -10}, 'weight 取值合法')
    chk(sum(1 for i in items if float(i['weight']) == 10) >= 2, '+10 条目 >= 2 条')
    q = sum(float(i['weight']) for i in items
            if float(i['weight']) > 0 and i['dimension'].startswith('内容质量'))
    chk(q / pos >= 0.3, f'内容质量正分占比 {q / pos:.0%} >= 30%')
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
