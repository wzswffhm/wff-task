"""Run the packaged verifier locally (no Docker) for NOP and Oracle evidence.

NOP: clean upstream baseline, no agent patch -> every F2P must fail.
Oracle: baseline plus the reference patch -> every F2P and P2P must pass.

Both runs use a fresh copy of sources/app and inject the held-out tests from
sources/verifier/tests, exactly like the containerised verifier does.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parent.parent / 'output' / 'deepSWE_2026-09-28-2-diskcache-atomic-write-batch'
APP = PACKAGE / 'sources' / 'app'
VERIFIER = PACKAGE / 'sources' / 'verifier'
RUNS = ROOT / 'runs'


def build_tree(name: str, patch: Path | None) -> Path:
    # Use a fresh directory per run: deleting the previous one is not
    # permitted here, and reusing it would mix evidence from two runs.
    stamp = subprocess.run(
        [sys.executable, '-c', 'import time;print(int(time.time()))'],
        capture_output=True, text=True,
    ).stdout.strip()
    tree = RUNS / ('%s-%s' % (name, stamp))
    tree.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(APP, tree / 'app')
    work = tree / 'app'
    if patch is not None:
        result = subprocess.run(
            [sys.executable, '-c',
             'import sys,subprocess;'
             'sys.exit(subprocess.run(["git","apply","--3way","--whitespace=nowarn",'
             'sys.argv[1]],cwd=".").returncode)',
             str(patch)],
            cwd=str(work), capture_output=True, text=True,
        )
        if result.returncode != 0:
            # git is unavailable or the tree is not a repo: fall back to patch(1)
            fallback = subprocess.run(['patch', '-p1', '-f', '-i', str(patch)],
                                      cwd=str(work), capture_output=True, text=True)
            if fallback.returncode != 0:
                raise SystemExit('reference patch failed to apply: %s\n%s'
                                 % (result.stderr[-500:], fallback.stdout[-500:]))
    tests = work / 'tests'
    shutil.copytree(VERIFIER / 'tests', tests, dirs_exist_ok=True)
    return work


def run(work: Path, logs: Path, label: str) -> int:
    logs.mkdir(parents=True, exist_ok=True)
    env_args = [sys.executable, str(VERIFIER / 'run_verifier.py'),
                '--app', str(work), '--logs', str(logs), '--skip-patch']
    result = subprocess.run(env_args, capture_output=True, text=True, cwd=str(work))
    (logs / 'stdout.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    print('===== %s =====' % label)
    print(result.stdout.strip()[-1200:])
    if result.stderr.strip():
        print('[stderr]', result.stderr.strip()[-600:])
    reward_file = logs / 'reward.json'
    if reward_file.is_file():
        data = json.loads(reward_file.read_text(encoding='utf-8'))
        print('reward=%s f2p=%s/%s p2p=%s/%s'
              % (data['reward'], data['f2p_passed'], data['f2p_total'],
                 data['p2p_passed'], data['p2p_total']))
        return data['reward']
    return -1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('nop', 'oracle', 'both'), default='both')
    args = parser.parse_args()

    rewards = {}
    stamp = subprocess.run(
        [sys.executable, '-c', 'import time;print(int(time.time()))'],
        capture_output=True, text=True,
    ).stdout.strip()
    if args.mode in ('nop', 'both'):
        work = build_tree('nop', None)
        rewards['nop'] = run(work, RUNS / ('nop-logs-%s' % stamp), 'NOP (clean baseline)')
    if args.mode in ('oracle', 'both'):
        work = build_tree('oracle', ROOT / 'reference.patch')
        rewards['oracle'] = run(work, RUNS / ('oracle-logs-%s' % stamp),
                                'ORACLE (reference patch)')

    print('===== summary =====')
    print(json.dumps(rewards, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
