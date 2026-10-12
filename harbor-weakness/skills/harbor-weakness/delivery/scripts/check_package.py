#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题包交付前静态自检（通用）。

对照 delivery/04-package-and-checklist.md §3 的 17 项中可静态验证的部分：
  #1 五件套齐全 / #2 solve.sh、test.sh 为 LF / #3 交付物文件名多处逐字节一致
  #4 打分项条数与维度覆盖 / #4b rubrics.json(设计态) 与 tests/rubrics.toml(运行态) 判分定义一致
  #7 task_id 三处一致 / #8 无真实密钥 / #9 无残留
  #10 文件名 <= 200 字节且无符号链接 / #12 prompt.md 含 {criteria} / #14 无不可见空白
  #15 [verifier.env] 的 judge 变量前缀与 [environment.env] 洁净

未能静态验证、须实机执行的项：#6 golden 预检、#13 镜像自检、#16 本地跑分、#17 交付文档。

用法:
    python3 check_package.py <题包目录>          # 单题目录（含 task.toml 的那一级）
"""
import sys, re, json, tomllib, pathlib, os, subprocess


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ROOT = pathlib.Path(argv[1]).resolve()
    if not (ROOT / 'task.toml').is_file():
        print(f'[FAIL] {ROOT} 下未找到 task.toml'); return 2
    errors, warns, oks = [], [], []

    # ---- #1 五件套齐全 ----
    need = ['instruction.md', 'task.toml', 'rubrics.json', 'environment/Dockerfile',
            'environment/requirements.txt', 'environment/input_files',
            'solution/solve.sh', 'solution/golden_output', 'tests/test.sh',
            'tests/finalize.py', 'tests/rubrics.toml', 'tests/prompt.md', 'tests/__golden_output']
    miss = [n for n in need if not (ROOT / n).exists()]
    if miss:
        errors.append(f'#1 缺组件: {miss}')
    else:
        oks.append('#1 五件套齐备')
    rt = ROOT / 'environment/requirements.txt'
    if rt.is_file() and rt.stat().st_size != 0:
        warns.append('#1 requirements.txt 非空（无执行侧依赖时应交空文件）')

    # ---- #2 LF + 可执行位 ----
    for f in ['solution/solve.sh', 'tests/test.sh']:
        fp = ROOT / f
        if not fp.is_file():
            continue
        if b'\r' in fp.read_bytes():
            errors.append(f'#2 {f} 含 CR（须 LF）')
        if not os.access(fp, os.X_OK):
            warns.append(f'#2 {f} 无可执行位')
    oks.append('#2 solve.sh / test.sh 换行与权限检查完成')

    # ---- 解析 task.toml ----
    tt = tomllib.loads((ROOT / 'task.toml').read_text(encoding='utf-8'))
    dpaths = {d['path'] for d in tt.get('metadata', {}).get('deliverables', [])}
    arts = {a.replace('/app/output/', '') for a in tt.get('artifacts', []) if a.startswith('/app/output/')}
    gold = {str(p.relative_to(ROOT / 'solution/golden_output')).replace('\\', '/')
            for p in (ROOT / 'solution/golden_output').rglob('*') if p.is_file()} \
        if (ROOT / 'solution/golden_output').exists() else set()
    gold2 = {str(p.relative_to(ROOT / 'tests/__golden_output')).replace('\\', '/')
             for p in (ROOT / 'tests/__golden_output').rglob('*') if p.is_file()} \
        if (ROOT / 'tests/__golden_output').exists() else set()
    inst_txt = (ROOT / 'instruction.md').read_text(encoding='utf-8') if (ROOT / 'instruction.md').is_file() else ''
    inst = set(re.findall(r'`([^`\s]+\.(?:md|py|png|xlsx|docx|pptx|csv|json))`', inst_txt))
    rtxt = (ROOT / 'tests/rubrics.toml').read_text(encoding='utf-8') if (ROOT / 'tests/rubrics.toml').is_file() else ''
    critf = {m[1] for m in re.findall(r'`(/app/output/)?([^`\s]+\.(?:md|py|png|xlsx|docx|pptx))`', rtxt)}
    critf = {c for c in critf if 'input_files' not in c}   # 输入材料引用不算交付物

    # ---- #3 交付物文件名一致 ----
    if dpaths:
        if arts != dpaths:
            errors.append(f'#3 artifacts 与 deliverables.path 不一致: 缺={sorted(dpaths-arts)} 多={sorted(arts-dpaths)}')
        for nm, s in [('solution/golden_output', gold), ('tests/__golden_output', gold2)]:
            if not (dpaths <= s):
                errors.append(f'#3 {nm} 缺交付物: {sorted(dpaths - s)}')
            extra = s - dpaths
            if extra:
                warns.append(f'#3 {nm} 含非交付物文件: {sorted(extra)}')
        if gold != gold2:
            errors.append('#3 solution/golden_output 与 tests/__golden_output 内容不一致')
        not_in_inst = dpaths - inst
        if not_in_inst:
            errors.append(f'#3 instruction.md 未列出的交付物: {sorted(not_in_inst)}')
        bad = {c for c in critf if c.split('/')[-1] not in {p.split('/')[-1] for p in dpaths}}
        if bad:
            warns.append(f'#3 rubrics.toml 引用的非交付物文件: {sorted(bad)}')
        # ---- #3b 判据描述里的交付物"非全名"写法 ----
        # 交付物基名共享 task-id 前缀时，rubric 描述中任何"去掉前缀"的写法都是隐患：
        # 若同条判据又要求"逐字一致"，会与 instruction.md / task.toml 的全名冲突，
        # 判官按字面比对即判 FAIL —— 连 oracle 也失分（FIN3-WKN-150 R01 实例：
        # 判据写"chart01 材料覆盖与数据缺口"，实际文件名是
        # FIN3-WKN-150_chart01_材料覆盖与数据缺口.png）。
        _bn = {p.split('/')[-1] for p in dpaths}
        _cp = os.path.commonprefix(sorted(_bn))
        _cp = _cp[:_cp.rfind('_') + 1] if '_' in _cp else ''
        if _cp and len(_cp) >= 4:
            _tails = set()
            for _b in _bn:
                if _b.startswith(_cp):
                    _t = _b[len(_cp):]
                    for _v in {_t, _t.rsplit('.', 1)[0]}:
                        if _v:
                            _tails.add(_v); _tails.add(_v.replace('_', ' '))
            _bad_forms = []
            for _t in sorted(_tails):
                for _m in re.finditer(re.escape(_t), rtxt):
                    _s = _m.start()
                    if _s >= len(_cp) and rtxt[_s - len(_cp):_s] == _cp:
                        continue          # 该写法是全名的一部分，合法
                    _bad_forms.append(_t); break
            if _bad_forms:
                warns.append('#3 rubrics.toml 出现交付物非全名写法'
                             f'（须写全名含前缀与扩展名）: {_bad_forms}')
        if not [e for e in errors if e.startswith('#3')]:
            oks.append(f'#3 交付物文件名多处逐字节一致（{len(dpaths)} 项）')

    # ---- #4 打分项（细则见 check_rubrics.py）----
    crit = tomllib.loads(rtxt).get('criterion', []) if rtxt else []
    if crit:
        pos = [c for c in crit if not c.get('negate')]
        oks.append(f'#4 打分项 {len(crit)} 条（正 {len(pos)} / 负 {len(crit)-len(pos)}）')
    else:
        warns.append('#4 tests/rubrics.toml 未解析到 criterion，请单独运行 check_rubrics.py')

    # ---- #4b rubrics.json(设计态) 与 tests/rubrics.toml(运行态) 判分定义一致 ----
    # 质检实例（FIN3-WKN-150，2026-10-05）：rubrics.json 的负向项只用负 weight 表示、
    # 缺 "negate": true，与 tests/rubrics.toml 的 negate=true 表示法不对应，被判为
    # "rubrics.json 与 tests/rubrics.toml 评分定义不一致"。运行态以 tests/rubrics.toml
    # 为准；设计态 rubrics.json 必须与其判据集合、负向集合、正分池逐一对齐。
    rp = ROOT / 'rubrics.json'
    if rp.is_file() and crit:
        try:
            jd = json.loads(rp.read_text(encoding='utf-8'))
        except Exception as e:
            jd = None
            errors.append(f'#4b rubrics.json 解析失败: {e}')
        if isinstance(jd, dict):
            jitems = [c for c in jd.get('items', []) if isinstance(c, dict)]
            jids = {c.get('id') for c in jitems}
            tids = {c.get('id') for c in crit}
            if jids != tids:
                errors.append(f'#4b rubrics.json 与 rubrics.toml 判据 id 集合不一致: '
                              f'仅 json={sorted(jids - tids)} 仅 toml={sorted(tids - jids)}')
            jneg = {c.get('id') for c in jitems if (c.get('weight') or 0) < 0 or c.get('negate')}
            tneg = {c.get('id') for c in crit if c.get('negate')}
            if jneg != tneg:
                errors.append(f'#4b 负向项集合不一致: json={sorted(jneg)} toml={sorted(tneg)}')
            miss_neg = [c.get('id') for c in jitems
                        if (c.get('weight') or 0) < 0 and c.get('negate') is not True]
            if miss_neg:
                errors.append('#4b rubrics.json 负向项缺 "negate": true'
                              f'（须负 weight + negate 双标记）: {sorted(miss_neg)}')
            jsmax = round(sum((c.get('weight') or 0) for c in jitems if not c.get('negate')), 6)
            tsmax = round(sum((c.get('weight') or 0) for c in crit if not c.get('negate')), 6)
            if abs(jsmax - tsmax) > 1e-6:
                errors.append(f'#4b 正分池 S_max 不一致: json={jsmax} toml={tsmax}')
            decl = (jd.get('metadata', {}) or {}).get('scoring', {}).get('s_max')
            if decl is not None and abs(float(decl) - tsmax) > 1e-6:
                errors.append(f'#4b metadata.scoring.s_max={decl} 与正分池 {tsmax} 不符')
            if not [e for e in errors if e.startswith('#4b')]:
                oks.append(f'#4b rubrics.json 与 rubrics.toml 判分定义一致'
                           f'（判据 {len(jitems)}，负向 {sorted(tneg)}，S_max {tsmax}）')
    elif not rp.is_file():
        warns.append('#4b 未找到 rubrics.json，跳过设计态/运行态一致性检查')

    # ---- #7 task_id 三处一致 ----
    tid = tt.get('metadata', {}).get('task_id', '')
    tname = tt.get('task', {}).get('name', '')
    norm = lambda s: re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    if tid and norm(ROOT.name) == norm(tid) == norm(tname.split('/')[-1]):
        oks.append(f'#7 task_id 三处一致: {ROOT.name} / {tid} / {tname}')
    else:
        errors.append(f'#7 task_id 不一致: 目录={ROOT.name} metadata.task_id={tid} task.name={tname}')

    # ---- #8 密钥扫描 ----
    pat = re.compile(r'(sk-[A-Za-z0-9\-_.]{16,}|ark-[0-9a-f]{8,}|cli_[a-z0-9]{12,})')
    hits = []
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.suffix.lower() in ('.png', '.jpg', '.zip', '.gz'):
            continue
        try:
            txt = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for mm in pat.finditer(txt):
            if '${' in txt[max(0, mm.start() - 3):mm.end() + 3]:
                continue
            hits.append(f'{p.relative_to(ROOT)}: {mm.group(0)[:16]}…')
    if hits:
        errors.append(f'#8 疑似真实密钥: {hits}')
    else:
        oks.append('#8 无真实密钥')

    # ---- #9 残留 ----
    # 例外：`跑分产物与轨迹/` 为验收口径要求的跑分归档目录（reward.json / reward-details.json
    # 须按 06 号文档原名归档，见交付文档 §4），该目录内不视为"本地跑测残留"。
    _ARCHIVE_DIR = '跑分产物与轨迹'
    bad_names = ('.git', '__pycache__', '.venv', '__MACOSX', '.DS_Store',
                 'reward.json', 'reward-details.json', 'reward_exit_message.json', 'jobs', 'logs')
    bad = [str(p.relative_to(ROOT)) for p in ROOT.rglob('*')
           if p.name in bad_names and _ARCHIVE_DIR not in p.relative_to(ROOT).parts]
    if bad:
        errors.append(f'#9 残留: {bad}')
    else:
        oks.append('#9 无残留')

    # ---- #10 文件名长度 / 符号链接 ----
    long = [p.name for p in ROOT.rglob('*') if len(p.name.encode('utf-8')) > 200]
    links = [str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_symlink()]
    if long:
        errors.append(f'#10 文件名超 200 字节: {long}')
    if links:
        errors.append(f'#10 存在符号链接: {links}')
    if not long and not links:
        oks.append('#10 文件名长度与符号链接检查通过')

    # ---- #12 prompt.md ----
    pt = (ROOT / 'tests/prompt.md').read_text(encoding='utf-8') if (ROOT / 'tests/prompt.md').is_file() else ''
    if '{criteria}' not in pt:
        errors.append('#12 tests/prompt.md 缺 {criteria} 占位符')
    else:
        tot = len(pt.encode('utf-8')) + sum(len(c.get('description', '').encode('utf-8')) for c in crit)
        if tot > 100 * 1024:
            errors.append(f'#12 prompt.md + 全部 description 总量 {tot/1024:.1f}KB > 100KB')
        else:
            oks.append(f'#12 prompt.md 含 {{criteria}}，总量 {tot/1024:.1f}KB')

    # ---- #14 不可见空白 ----
    # 例外：`跑分产物与轨迹/` 归档目录内的模型原始交付物（如 qwen 备忘录）可能含 U+00A0/U+3000，
    # 属模型正常输出，非题目核心文件问题；与 #9 同口径豁免该目录。
    inv = re.compile(r'[\u00a0\u3000]')
    inv_hits = []
    for p in list(ROOT.rglob('*.toml')) + list(ROOT.rglob('*.md')) + list(ROOT.rglob('*.json')):
        if _ARCHIVE_DIR in p.relative_to(ROOT).parts:
            continue
        if p.is_file() and inv.search(p.read_text(encoding='utf-8', errors='ignore')):
            inv_hits.append(str(p.relative_to(ROOT)))
    if inv_hits:
        errors.append(f'#14 含不可见空白(U+00A0/U+3000): {inv_hits}')
    else:
        oks.append('#14 无不可见空白')

    # ---- #15 verifier.env / environment.env ----
    venv = tt.get('verifier', {}).get('env', {})
    eenv = tt.get('environment', {}).get('env', {})
    ok15 = True
    for k in venv:
        if 'JUDGE' in k and not k.startswith('JUDGE_'):
            errors.append(f'#15 [verifier.env].{k} 未用 JUDGE_ 前缀'); ok15 = False
    for k in eenv:
        if 'JUDGE' in k:
            errors.append(f'#15 [environment.env] 不应出现 {k}（JUDGE_* 只写 [verifier.env]）'); ok15 = False
    if ok15:
        oks.append(f'#15 verifier.env {len(venv)} 项 / environment.env {len(eenv)} 项')

    for o in oks:
        print('  OK   ' + o)
    for w in warns:
        print('  !    ' + w)
    for e in errors:
        print('  X    ' + e)
    print('\n[PASS] 静态自检通过（#6/#13/#16/#17 须实机执行）'
          if not errors else f'\n[FAIL] {len(errors)} 项错误')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
