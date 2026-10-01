#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G3 评分器门禁静态校验（通用）。

对照 delivery/04-package-and-checklist.md §3 的第 4/5/11 项：
  - weight 只出现 3.0 / 7.0 / 10.0，且无负 weight（负向须用 negate = true + 正 weight）
  - type 只出现 binary / likert；likert 必须 points = 5 且 description 含 5/4/3/2/1 档位锚点
  - name 与 id 相同；description 必须带交付物路径清单（"Deliverables to inspect:"）
  - Critically Important（weight = 10）>= 2 条；内容质量维度正分占比 >= 30%
  - [judge] 段固定值

用法:
    python3 check_rubrics.py <题包目录>/tests/rubrics.toml
维度取自同题包根目录的 rubrics.json（可选；缺失时跳过占比检查）。
"""
import sys, json, tomllib, pathlib


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    p = pathlib.Path(argv[1])
    d = tomllib.loads(p.read_text(encoding='utf-8'))
    crit = d.get('criterion', [])
    errs, warns = [], []

    dim_map = {}
    jp = p.parent.parent / 'rubrics.json'
    if jp.is_file():
        try:
            for c in json.loads(jp.read_text(encoding='utf-8')).get('criteria', []):
                dim_map[c['id']] = c.get('dimension', '')
        except Exception as e:
            warns.append(f'rubrics.json 解析失败，跳过维度检查: {e}')

    j = d.get('judge', {})
    for k, v in [('judge', 'claude-code'), ('prompt_template', 'prompt.md'),
                 ('mode', 'individual'), ('weight', 1.0)]:
        if j.get(k) != v:
            errs.append(f'[judge].{k} 应为 {v!r}，实际 {j.get(k)!r}')

    ALLOWED_W = {3.0, 7.0, 10.0}
    qs_pos = total_pos = 0.0
    crit10 = npos = nneg = 0
    for c in crit:
        i = c.get('id')
        if c.get('name') != i:
            errs.append(f'{i}: name({c.get("name")!r}) != id')
        w = float(c.get('weight', 0))
        neg = bool(c.get('negate'))
        if w < 0:
            errs.append(f'{i}: weight 为负 ({w}) —— 严禁负 weight，请改用 negate = true')
        if abs(w) not in ALLOWED_W:
            errs.append(f'{i}: weight={w} 不在允许档位 {sorted(ALLOWED_W)}')
        t = c.get('type')
        if t not in ('binary', 'likert'):
            errs.append(f'{i}: type={t!r} 非法（仅 binary / likert）')
        if t == 'likert' and c.get('points') != 5:
            errs.append(f'{i}: likert 必须 points = 5，实际 {c.get("points")!r}')
        desc = c.get('description', '')
        if 'Deliverables to inspect:' not in desc:
            errs.append(f'{i}: description 缺少 "Deliverables to inspect:"')
        if t == 'likert':
            for a in ('5=', '4=', '3=', '2=', '1='):
                if a not in desc:
                    warns.append(f'{i}: 可能缺少 {a} 档位锚点')
        if neg:
            nneg += 1
        else:
            npos += 1
            total_pos += w
            if w == 10.0:
                crit10 += 1
            if '内容质量' in dim_map.get(i, ''):
                qs_pos += w

    if crit10 < 2:
        errs.append(f'Critically Important（weight = 10）仅 {crit10} 条，要求 >= 2')
    share = qs_pos / total_pos if total_pos else 0.0
    if dim_map and share < 0.30:
        errs.append(f'内容质量维度正分占比 {share:.1%} < 30%')

    print(f'criteria 条数: {len(crit)}  (正向 {npos} / 负向 {nneg})')
    print(f'正向 S_max: {total_pos:.1f} | Critically Important(10.0): {crit10} 条 | 内容质量正分占比: {share:.1%}')
    print(f'负向条目: {[c["id"] for c in crit if c.get("negate")]}')
    for w_ in warns:
        print('  ! warn:', w_)
    for e in errs:
        print('  X', e)
    print('\n[PASS] G3 评分器门禁全部通过' if not errs else f'\n[FAIL] {len(errs)} 项不通过')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
