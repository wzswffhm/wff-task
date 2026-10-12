#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 fix9（2026-10-11 质检报告(2) 金标三处修正轮）的判分结果归档为批次包结构。

来源（混合）：
  - oracle：fix9 新 trial（修复后金标 G4=1.0，harbor trial start 跑）
  - 三模型：fix8 正式 trial 的 agent 产物（复用）+ fix9 rejudge 判分（_rejudge/<model>/verifier）

归档布局（同 fix8）：
  <batch>/FIN3-WKN-149/跑分产物与轨迹/
      summary.json
      <executor>/{output/, reward.json, reward-details.json, 轨迹/}
"""
import json
import pathlib
import re
import shutil
import sys

WSL_ROOT = pathlib.Path('/mnt/c/Users/Administrator/Desktop/wff-task')
H = WSL_ROOT / 'harbor-weakness'
BATCH = H / 'work_fin-b01_20261009_fix8-149'   # 复用 fix8 批次名（本轮为该批次的金标修正轮）
ARCH = BATCH / 'FIN3-WKN-149' / '跑分产物与轨迹'

ORACLE_TRIAL = pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix9/trials-oracle/FIN3-WKN-149__DRcKq7u')
REJUDGE = H / 'FIN3-WKN-149' / '_rejudge'
# 三模型：fix8 trial 的 agent 产物
FIX8_TRIAL_OUTPUT = {
    'qwen3.8-max-0902': pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-qwen/FIN3-WKN-149__uqNx7ti'),
    'gpt-5.6-sol': pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-gpt/FIN3-WKN-149__qsFcMtD'),
    'claude-opus-4-8': pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-opus/FIN3-WKN-149__vTPHQTW'),
}

SK = re.compile(r'sk-[A-Za-z0-9._\-]{12,}')
BEARER = re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{20,}')


def desensitize(text: str) -> str:
    text = SK.sub('<REDACTED_CREDENTIAL>', text)
    text = BEARER.sub(r'\1<REDACTED_CREDENTIAL>', text)
    return text.replace('\u3000', ' ').replace('\u00a0', ' ')


def read_reward(p: pathlib.Path):
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return None


def copy_traces(trial_dir: pathlib.Path, dest: pathlib.Path, tag: str):
    dest.mkdir(parents=True, exist_ok=True)
    names = ['claude-code.txt', 'trajectory.json'] if tag != 'oracle' else ['oracle.txt']
    for f in names:
        src = trial_dir / 'agent' / f
        if src.is_file():
            (dest / f).write_text(
                desensitize(src.read_text(encoding='utf-8', errors='ignore')), encoding='utf-8')
    tl = trial_dir / 'trial.log'
    if tl.is_file():
        (dest / 'trial.log').write_text(
            desensitize(tl.read_text(encoding='utf-8', errors='ignore')), encoding='utf-8')


def main():
    if ARCH.exists():
        shutil.rmtree(ARCH)
    ARCH.mkdir(parents=True)

    summary = {
        'task': 'FIN3-WKN-149',
        'batch': BATCH.name,
        'task_version': '1.0.8',
        'round': 'fix9 (2026-10-11 质检报告(2) 金标三处计算修正轮)',
        'scoring': ('金标修正轮：修正 reproduce.py 三处计算错误（cgb_shock_bp 单位 /100→/10000、'
                    '历史校准境内权益逐项加权、标普500美元收益反算补 +1/-1）并补 rubrics [scoring] '
                    'aggregation=weighted_mean 后重跑；oracle 新跑（G4），三模型复用 fix8 agent 产物重判官；'
                    '判官 qwen3.7-plus，mode=individual，36 条判据逐条 individual 会话'),
        'judge': {'model': 'qwen3.7-plus', 'provider': 'anthropic', 'mode': 'individual'},
        'archive_layout': ('交付文档与跑分产物归档于题目目录内：'
                           '<batch>/FIN3-WKN-149/{五件套, 交付文档.md, 跑分产物与轨迹/}'),
        'trajectory_policy': ('依交付规范归档 agent 轨迹：每个执行体归档其采用轮次的完整轨迹于 轨迹/'
                              '（claude-code.txt / trajectory.json / trial.log），不做删改。'),
        'executors': {},
        'notes': [],
    }
    zero_report = {}

    # ---- oracle（fix9 trial） ----
    ex_dir = 'oracle'
    out = ARCH / ex_dir
    (out / '轨迹').mkdir(parents=True, exist_ok=True)
    rj = read_reward(ORACLE_TRIAL / 'verifier' / 'reward.json')
    if rj:
        (out / 'reward.json').write_text(json.dumps(rj, ensure_ascii=False, indent=2), encoding='utf-8')
        summary['executors'][ex_dir] = {
            'trial': ORACLE_TRIAL.name, 'source': 'fix9 new trial',
            **{k: rj.get(k) for k in ('reward', 'graded_score', 'criteria_counted', 'verifier_error')}}
        print(f'[OK] oracle: trial={ORACLE_TRIAL.name} reward={rj.get("reward")}')
    else:
        summary['notes'].append('oracle: fix9 trial reward 缺失')
        print('[MISS] oracle reward')
    rd = ORACLE_TRIAL / 'verifier' / 'graded' / 'reward-details.json'
    if rd.is_file():
        shutil.copy2(rd, out / 'reward-details.json')
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
        zero_report[ex_dir] = {'graded_score': det.get('score') or det.get('graded_score'),
                               'zero_count': len(zeros), 'zeros': [f'{i}({w:g})' for i, w in zeros]}
    art = ORACLE_TRIAL / 'artifacts' / 'app' / 'output'
    if art.is_dir():
        shutil.copytree(art, out / 'output', dirs_exist_ok=True)
    copy_traces(ORACLE_TRIAL, out / '轨迹', 'oracle')
    (out / '轨迹' / '说明.txt').write_text(
        'oracle 试次（fix9 金标修正轮）执行修复后 solution/solve.sh，不产生 claude-code 轨迹；\n'
        '本目录保留 harbor oracle agent 日志（oracle.txt）与试次日志（trial.log）作为运行记录；\n'
        '金标准产物见 ../output/，评分结果见 ../reward.json 与 ../reward-details.json。\n',
        encoding='utf-8')

    # ---- 三模型（fix8 产物 + fix9 rejudge 判分） ----
    for ex_dir in ['qwen3.8-max-0902', 'gpt-5.6-sol', 'claude-opus-4-8']:
        out = ARCH / ex_dir
        (out / '轨迹').mkdir(parents=True, exist_ok=True)
        # reward 来自 rejudge
        rr = read_reward(REJUDGE / ex_dir / 'verifier' / 'reward.json')
        em = REJUDGE / ex_dir / 'verifier' / 'reward_exit_message.json'
        valid = rr and float(rr.get('criteria_counted') or 0) >= 1 and float(rr.get('verifier_error') or 0) == 0.0
        if valid:
            (out / 'reward.json').write_text(json.dumps(rr, ensure_ascii=False, indent=2), encoding='utf-8')
            trial_dir = FIX8_TRIAL_OUTPUT[ex_dir]
            summary['executors'][ex_dir] = {
                'trial': trial_dir.name, 'source': 'fix8 agent 产物 + fix9 rejudge',
                **{k: rr.get(k) for k in ('reward', 'graded_score', 'criteria_counted', 'verifier_error')}}
            print(f'[OK] {ex_dir}: reward={rr.get("reward")}')
        else:
            summary['notes'].append(f'{ex_dir}: rejudge reward 未有效（{"exit="+str(em.name) if em.is_file() else "无分"}）')
            print(f'[MISS] {ex_dir}: rejudge 未出分')
        # reward-details 来自 rejudge
        rd = REJUDGE / ex_dir / 'verifier' / 'graded' / 'reward-details.json'
        if rd.is_file():
            shutil.copy2(rd, out / 'reward-details.json')
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
            zero_report[ex_dir] = {'graded_score': det.get('score') or det.get('graded_score'),
                                   'zero_count': len(zeros), 'zeros': [f'{i}({w:g})' for i, w in zeros]}
        # 产物来自 fix8 trial
        art = FIX8_TRIAL_OUTPUT[ex_dir] / 'artifacts' / 'app' / 'output'
        if art.is_dir():
            shutil.copytree(art, out / 'output', dirs_exist_ok=True)
        # 轨迹来自 fix8 trial
        copy_traces(FIX8_TRIAL_OUTPUT[ex_dir], out / '轨迹', 'model')

    # ---- 均分 ----
    means = [v['reward'] for k, v in summary['executors'].items()
             if k != 'oracle' and v.get('reward') is not None]
    summary['model_mean'] = sum(means) / len(means) if means else None
    summary['mean_gate'] = '<0.70'
    summary['gate_pass'] = bool(means) and summary['model_mean'] < 0.70

    (ARCH / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n=== summary ===')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('\n=== 零分分布 ===')
    print(json.dumps(zero_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
