#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G3 评分器门禁静态校验（通用）。

对照 delivery/04-package-and-checklist.md §3 的第 4/5/11 项：
  - weight 只出现 3.0 / 7.0 / 10.0，且无负 weight（负向须用 negate = true + 正 weight）
  - type 只出现 binary / likert；likert 必须 points = 5 且 description 含 5/4/3/2/1 档位锚点
  - name 与 id 相同；description 必须带交付物路径清单（"Deliverables to inspect:"）
  - Critically Important（weight = 10）>= 2 条；内容质量维度正分占比 >= 30%
  - [judge] 段固定值
  - 设计态 rubrics.json 里每个 gradient 条目的 levels 键必须恰为比例键 {0, 0.25, 0.5, 0.75, 1}
    （绝不是判官侧整数 5/4/3/2/1；后者会被 package validator / preflight 判 FAIL）

用法:
    python3 check_rubrics.py <题包目录>/tests/rubrics.toml
维度与设计态 levels 取自同题包根目录的 rubrics.json（可选；缺失时跳过对应检查）。
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

    GRADIENT_KEYS = {'0', '0.25', '0.5', '0.75', '1'}
    dim_map = {}
    grad_ok = []
    jp = p.parent.parent / 'rubrics.json'
    if jp.is_file():
        try:
            _jd = json.loads(jp.read_text(encoding='utf-8'))
            # rubrics.json 顶层 key：返修后为 items（验收口径），旧版为 criteria；两者兼容
            for c in (_jd.get('items') or _jd.get('criteria') or []):
                dim_map[c['id']] = c.get('dimension', '')
                # 设计态 gradient 的 levels 键必须为比例键 {0,0.25,0.5,0.75,1}；
                # 判官侧整数 5/4/3/2/1 只出现在 tests/rubrics.toml 的 description 锚点里。
                if str(c.get('type', '')).lower() == 'gradient':
                    lv = c.get('levels')
                    if not isinstance(lv, dict):
                        errs.append(f"{c['id']}: 设计态 rubrics.json 的 gradient 必须写 levels 对象"
                                    f"（键为比例键 1/0.75/0.5/0.25/0），实际为 {type(lv).__name__}")
                    else:
                        ks = {str(k) for k in lv}
                        if ks != GRADIENT_KEYS:
                            errs.append(f"{c['id']}: gradient levels 键 {sorted(ks)} 非法，"
                                        f"必须恰为 {sorted(GRADIENT_KEYS)}（比例键，"
                                        f"不是判官侧整数 5/4/3/2/1）")
                        else:
                            grad_ok.append(c['id'])
                elif c.get('levels') not in (None, {}, []):
                    warns.append(f"{c['id']}: 非 gradient 条目不应写 levels")
        except Exception as e:
            warns.append(f'rubrics.json 解析失败，跳过维度/levels 检查: {e}')

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
    if grad_ok:
        print(f'设计态 gradient levels 比例键校验通过: {grad_ok}')
    for w_ in warns:
        print('  ! warn:', w_)
    for e in errs:
        print('  X', e)
    print('\n[PASS] G3 评分器门禁全部通过' if not errs else f'\n[FAIL] {len(errs)} 项不通过')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
