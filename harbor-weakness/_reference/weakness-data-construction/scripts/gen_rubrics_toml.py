#!/usr/bin/env python3
"""rubrics.json → Harbor tests/rubrics.toml（RL0-1 / rewardkit 落地口径）。

用法:
    python gen_rubrics_toml.py <task-dir> [--check]

要点（详见 references/rewardkit-conversion.md）：
  1. 负分条 → negate = true + 正 weight，description 恢复为直接描述违规行为；
  2. likert 只保留 1–5 整数标度，锚点唯一来源是 rubrics.json 的 levels；
     description 里残留的旧 0–1 档位段（"按…评分：1=…；0.75=…"）会被删除；
  3. 每条 description 末尾只追加一段 "Deliverables to inspect: ..."；
  4. 输出 LF、无不可见空白；--check 只校验不写盘。
"""
import json
import os
import re
import sys

LEVEL_ORDER = ['1', '0.75', '0.5', '0.25', '0']
ANCHOR = ['5', '4', '3', '2', '1']
TAIL = re.compile(r'按[^。；]{0,12}评分：')


def load_items(task_dir):
    raw = json.load(open(os.path.join(task_dir, 'rubrics.json'), encoding='utf-8'))
    return raw['items'] if isinstance(raw, dict) else raw


def deliverable_list(task_dir):
    out = []
    for line in open(os.path.join(task_dir, 'task.toml'), encoding='utf-8'):
        s = line.strip()
        if s.startswith('"/app/output/'):
            out.append(s.strip(',').strip('"').replace('/app/output/', 'output/'))
    if not out:
        raise SystemExit('task.toml 的 artifacts 里没有 /app/output/ 条目')
    return out


def clean(s):
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.replace('。。', '。').replace('。；', '；')
    return s


def strip_old_scale(desc):
    """删掉 description 里残留的 0-1 档位段（锚点由 levels 提供）。"""
    m = TAIL.search(desc)
    if not m:
        return desc
    head, rest = desc[:m.start()], desc[m.end():]
    # 只有确实跟着 "1=" 之类的档位内容时才视为档位段
    if re.match(r'\s*1\s*=', rest):
        return head
    return head + rest


def anchors(levels):
    missing = [k for k in LEVEL_ORDER if k not in levels]
    if missing:
        raise SystemExit(f'levels 缺档位 {missing}')
    parts = []
    for old, new in zip(LEVEL_ORDER, ANCHOR):
        txt = re.sub(r'[；;，,、。\s]+$', '', clean(str(levels[old])))
        parts.append(f'{new}={txt}')
    return '；'.join(parts) + '。'


def build(task_dir):
    items = load_items(task_dir)
    arts = deliverable_list(task_dir)
    inspect = 'Deliverables to inspect: ' + ', '.join(f'`{a}`' for a in arts) + '.'
    lines = ['[judge]', 'judge = "claude-code"', 'prompt_template = "prompt.md"',
             'model = "qwen3.7-plus"', 'timeout = 7200', 'weight = 1.0',
             'mode = "individual"', '', '[scoring]',
             'aggregation = "weighted_mean"', '']
    for it in items:
        w = float(it['weight'])
        desc = clean(strip_old_scale(it['description']))
        # 有些题包的 description 里已经写好了交付物清单（历史口径），不要重复追加
        tail = '' if 'Deliverables to inspect:' in desc else f' {inspect}'
        if desc.count('Deliverables to inspect:') > 1:
            raise SystemExit(f'{it["id"]} 的 description 里出现了多段交付物清单')
        if w < 0:
            body = [f'id = "{it["id"]}"', f'name = "{it["id"]}"',
                    'description = ' + json.dumps(
                        f'{desc} 仅当发现明确证据证明该情形存在时判定成立。{tail}'.strip(),
                        ensure_ascii=False),
                    'type = "binary"', 'negate = true', f'weight = {abs(w):.1f}']
        elif str(it['type']).lower() == 'gradient':
            lv = it.get('levels')
            if not lv:
                raise SystemExit(f'{it["id"]} 是 gradient 但没有 levels')
            body = [f'id = "{it["id"]}"', f'name = "{it["id"]}"',
                    'description = ' + json.dumps(
                        f'{desc} 评分为 1–5 整数：{anchors(lv)}{tail}',
                        ensure_ascii=False),
                    'type = "likert"', 'points = 5', f'weight = {w:.1f}']
        else:
            body = [f'id = "{it["id"]}"', f'name = "{it["id"]}"',
                    'description = ' + json.dumps(f'{desc}{tail}'.strip(),
                                                  ensure_ascii=False),
                    'type = "binary"', f'weight = {w:.1f}']
        lines.append('[[criterion]]')
        lines.extend(body)
        lines.append('')
    return '\n'.join(lines), len(items)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    task_dir = sys.argv[1].rstrip('/\\')
    text, n = build(task_dir)
    bad = [c for c in ('\u00a0', '\u3000') if c in text]
    if bad:
        raise SystemExit('生成的 toml 含不可见空白字符')
    for token in ('。；', '。。', 'Deliverables to inspect: ``'):
        if token in text:
            raise SystemExit(f'生成的 toml 含异常片段: {token}')
    if '--check' in sys.argv:
        print(f'[check] OK，{n} 条 criteria，{len(text.encode("utf-8"))} bytes')
        return
    out = os.path.join(task_dir, 'tests', 'rubrics.toml')
    open(out, 'w', encoding='utf-8', newline='\n').write(text)
    print(f'written {out}  {len(text.encode("utf-8"))} bytes, {n} criteria')


if __name__ == '__main__':
    main()
