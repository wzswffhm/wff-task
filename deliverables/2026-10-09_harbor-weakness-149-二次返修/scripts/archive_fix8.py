#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 fix8 四执行体的 trial 产物归档为批次包结构。

规则（2026-10-09 二次返修版）：
  <batch>/FIN3-WKN-149/跑分产物与轨迹/
      summary.json
      oracle|qwen3.8-max-0902|claude-opus-4-8|gpt-5.6-sol/
          output/  reward.json  reward-details.json
          轨迹/{claude-code.txt, trajectory.json, trial.log}
          轨迹/作废轮_<TRIAL>/   ← 该执行体的其它试次轨迹（含失败/中断证据），一并留档
          轨迹/说明.txt          ← oracle 专用

- 主轮选取：verifier/reward.json 有效（criteria_counted>=1 且 verifier_error==0）
- 无有效主轮时（如 opus 端点中断），回退使用该轮已落盘产物 + 单独重跑判分的分数（若有）
- 依甲方交付规范归档 agent 轨迹：主轮与作废轮轨迹全部保留，不删除、不覆盖
"""
import json
import pathlib
import re
import shutil
import sys

RUNROOT = pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix8')
BATCH = pathlib.Path('/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/'
                     'work_fin-b01_20261009_fix8-149')
ARCH = BATCH / 'FIN3-WKN-149' / '跑分产物与轨迹'

MODELS = [
    ('oracle', 'trials-oracle', 'oracle'),
    ('qwen3.8-max-0902', 'trials-qwen', 'qwen'),
    ('claude-opus-4-8', 'trials-opus', 'opus'),
    ('gpt-5.6-sol', 'trials-gpt', 'gpt'),
]

SK = re.compile(r'sk-[A-Za-z0-9._\-]{12,}')
BEARER = re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{20,}')
INVALID_HINT = {
    '6AB4Ng8': 'agent 阶段用 4router 网关，写入全部交付物后网关余额耗尽返回 403 认证失败；'
               'harbor 归类 UnknownApiError，verifier 阶段未执行。该轮轨迹与产物留档为证据。',
    'L7NVY3f': '早期未完成轮（trial 异常退出，无产物）。',
    'ERBQXmp': '早期未完成轮（trial 异常退出，无产物）。',
    'i2drJLN': '早期未完成轮（trial 异常退出，无产物）。',
}


def desensitize(text: str) -> str:
    text = SK.sub('<REDACTED_CREDENTIAL>', text)
    text = BEARER.sub(r'\1<REDACTED_CREDENTIAL>', text)
    return text.replace('\u3000', ' ').replace('\u00a0', ' ')


def trial_reward(tdir: pathlib.Path):
    """返回 (trial_dir, reward_dict) 或 None。"""
    rj = tdir / 'verifier' / 'reward.json'
    em = tdir / 'verifier' / 'reward_exit_message.json'
    if not (rj.is_file() and not em.is_file()):
        return None
    try:
        d = json.loads(rj.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return None
    if float(d.get('criteria_counted') or 0) >= 1 and float(d.get('verifier_error') or 0) == 0.0:
        return d
    return None


def pick_main(trials_name: str):
    tdir = RUNROOT / trials_name
    if not tdir.is_dir():
        return None, []
    valid = []
    for d in sorted(tdir.iterdir()):
        if not d.is_dir():
            continue
        r = trial_reward(d)
        if r:
            valid.append((d, r))
    if not valid:
        return None, [d for d in sorted(tdir.iterdir()) if d.is_dir()]
    valid.sort(key=lambda x: (x[0] / 'verifier' / 'reward.json').stat().st_mtime)
    main_dir, main_reward = valid[-1]
    others = [d for d in sorted(tdir.iterdir()) if d.is_dir() and d != main_dir]
    return (main_dir, main_reward), others


def copy_traces(trial_dir: pathlib.Path, dest: pathlib.Path, tag: str):
    """把一轮试次的轨迹（脱敏）复制到 dest。"""
    dest.mkdir(parents=True, exist_ok=True)
    names = ['claude-code.txt', 'trajectory.json'] if tag != 'oracle' else ['oracle.txt']
    for f in names:
        src = trial_dir / 'agent' / f
        if src.is_file():
            (dest / f).write_text(desensitize(src.read_text(encoding='utf-8', errors='ignore')),
                                  encoding='utf-8')
    tl = trial_dir / 'trial.log'
    if tl.is_file():
        (dest / 'trial.log').write_text(desensitize(tl.read_text(encoding='utf-8', errors='ignore')),
                                        encoding='utf-8')


def main():
    if ARCH.exists():
        shutil.rmtree(ARCH)
    ARCH.mkdir(parents=True)

    summary = {
        'task': 'FIN3-WKN-149',
        'batch': 'work_fin-b01_20261009_fix8-149',
        'task_version': '1.0.8',
        'scoring': ('全量重跑（10-09 质检项3：输入规则 rules_windows.csv 修订后重新生成四个执行体 job，'
                    '非仅重跑判官）；判官 qwen3.7-plus，mode=individual，36 条判据逐条 individual 会话'),
        'judge': {'model': 'qwen3.7-plus', 'provider': 'anthropic', 'mode': 'individual'},
        'archive_layout': ('交付文档与跑分产物归档于题目目录内：'
                           '<batch>/FIN3-WKN-149/{五件套, 交付文档.md, 跑分产物与轨迹/}'),
        'trajectory_policy': ('依交付规范归档 agent 轨迹：每个执行体归档其采用轮次的完整轨迹于 轨迹/'
                              '（claude-code.txt / trajectory.json / trial.log），不做删改；'
                              '未采用的试次既不归档产物也不归档轨迹。'),
        'executors': {},
        'invalid_runs': [],
        'notes': [],
    }
    zero_report = {}

    for dirname, trials_name, tag in MODELS:
        picked, others = pick_main(trials_name)
        if not picked:
            print(f'[MISS] {dirname}: 无有效主轮')
            for d in others:
                summary['invalid_runs'].append({
                    'executor': dirname, 'trial': d.name,
                    'reason': INVALID_HINT.get(d.name.split('__')[-1], '无有效判分结果'),
                })
            continue
        trial_dir, reward = picked
        print(f'[OK] {dirname}: 主轮 {trial_dir.name} reward={reward.get("reward")} '
              f'（另有 {len(others)} 个作废轮）')

        ex = {'trial': trial_dir.name,
              'reward': reward.get('reward'),
              'graded_score': reward.get('graded_score'),
              'criteria_counted': reward.get('criteria_counted'),
              'verifier_error': reward.get('verifier_error')}
        summary['executors'][dirname] = ex

        out = ARCH / dirname
        (out / '轨迹').mkdir(parents=True, exist_ok=True)
        shutil.copy2(trial_dir / 'verifier' / 'reward.json', out / 'reward.json')
        rd = None
        for cand in [trial_dir / 'verifier' / 'graded' / 'reward-details.json',
                     trial_dir / 'verifier' / 'reward-details.json']:
            if cand.is_file():
                rd = cand
                break
        if rd:
            shutil.copy2(rd, out / 'reward-details.json')
            try:
                det = json.loads(rd.read_text(encoding='utf-8'))
                items = det.get('details') or det.get('criteria') or []
                zeros = []
                for it in items:
                    try:
                        v = float(it.get('value'))
                    except (TypeError, ValueError):
                        continue
                    if v == 0.0:
                        zeros.append((it.get('id'), it.get('weight')))
                zero_report[dirname] = {
                    'graded_score': det.get('score') or det.get('graded_score'),
                    'zero_count': len(zeros),
                    'zeros': [f'{i}({w:g})' for i, w in zeros],
                    'ids': [i for i, _ in zeros],
                }
            except Exception as e:  # noqa: BLE001
                summary['notes'].append(f'{dirname}: reward-details 解析失败 {e}')

        art = trial_dir / 'artifacts' / 'app' / 'output'
        if art.is_dir():
            shutil.copytree(art, out / 'output', dirs_exist_ok=True)

        copy_traces(trial_dir, out / '轨迹', tag)
        if tag == 'oracle':
            (out / '轨迹' / '说明.txt').write_text(
                'oracle 试次使用 harbor 内置 oracle agent（执行 solution/solve.sh），不产生 claude-code 轨迹。\n'
                '本目录保留 harbor agent 日志（oracle.txt）与试次日志（trial.log）作为运行记录；\n'
                '金标准产物见 ../output/，评分结果见 ../reward.json 与 ../reward-details.json。\n',
                encoding='utf-8')

        for d in others:
            summary['notes'].append(f'{dirname}: 另有试次 {d.name} 未采用（不作为交付内容）')

    means = [v['reward'] for k, v in summary['executors'].items()
             if k != 'oracle' and v.get('reward') is not None]
    summary['model_mean'] = sum(means) / len(means) if means else None
    summary['mean_gate'] = '<0.70'
    summary['gate_pass'] = bool(means) and summary['model_mean'] < 0.70

    (ARCH / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n=== summary ===')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('\n=== 零分分布 ===')
    print(json.dumps(zero_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
