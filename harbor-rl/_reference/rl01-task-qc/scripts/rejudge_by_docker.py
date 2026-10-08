#!/usr/bin/env python3
"""只重跑判官、不重跑 agent —— 用题包 tests/ 与已落盘交付物重算分数。

用法:
    python rejudge_by_docker.py <task-dir> <镜像> <执行体>=<交付物目录> [...]

例:
    python rejudge_by_docker.py ./LAW-004 zq-law004:latest \
        oracle=./LAW-004/solution/golden_output \
        qwen=/path/to/job/qwen/artifacts/app/output

凭据从环境变量 JUDGE_API_KEY / JUDGE_BASE_URL 读取（或 --creds <env 文件> 指定
形如 KEY=VALUE 的文件）。结果落在 <task-dir>/_rejudge/<执行体>/verifier/。

前提：题面 instruction.md 未变（agent 产物仍然有效）；判据、prompt.md 或参考答案改动后
必须重跑，否则交付的逐条判分记录与判据对不上。
"""
import os
import subprocess
import sys


def load_creds(path):
    env = {}
    if path and os.path.isfile(path):
        for ln in open(path, encoding='utf-8-sig'):
            ln = ln.strip()
            if ln and not ln.startswith('#') and '=' in ln:
                k, v = ln.split('=', 1)
                env[k.strip()] = v.strip()
    return env


def main():
    argv = sys.argv[1:]
    creds_file = None
    if '--creds' in argv:
        i = argv.index('--creds')
        creds_file = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) < 3:
        raise SystemExit(__doc__)
    task_dir = os.path.abspath(argv[0].rstrip('/\\'))
    image = argv[1]
    pairs = argv[2:]

    creds = dict(os.environ)
    creds.update(load_creds(creds_file))
    for k in ('JUDGE_API_KEY', 'JUDGE_BASE_URL'):
        if not creds.get(k):
            raise SystemExit(f'缺少 {k}（用 --creds 指定凭据文件或设为环境变量）')

    base = os.path.join(task_dir, '_rejudge')
    for pair in pairs:
        who, art = pair.split('=', 1)
        art = os.path.abspath(art)
        if not os.path.isdir(art):
            raise SystemExit(f'交付物目录不存在: {art}')
        logs = os.path.join(base, who)
        os.makedirs(logs, exist_ok=True)
        name = f'rejudge-{os.path.basename(task_dir)}-{who}'
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        args = ['docker', 'run', '--rm', '--name', name,
                '-v', f"{os.path.join(task_dir, 'tests')}:/tests",
                '-v', f"{os.path.join(task_dir, 'environment', 'input_files')}:/app/input_files:ro",
                '-v', f'{art}:/app/output',
                '-v', f'{logs}:/logs',
                '-e', f"JUDGE_API_KEY={creds['JUDGE_API_KEY']}",
                '-e', f"JUDGE_BASE_URL={creds['JUDGE_BASE_URL']}",
                '-e', f"JUDGE_MODEL={creds.get('JUDGE_MODEL', 'qwen3.7-plus')}",
                '-e', f"JUDGE_API_PROTOCOL={creds.get('JUDGE_API_PROTOCOL', 'anthropic')}",
                '-e', 'LITELLM_LOCAL_MODEL_COST_MAP=True',
                '-e', 'LITELLM_DROP_PARAMS=true',
                image,
                'bash', '-c',
                "sed -i 's/\\r$//' /tests/*.sh /tests/*.py 2>/dev/null; bash /tests/test.sh"]
        creation = 0x08000000 if os.name == 'nt' else 0   # CREATE_NO_WINDOW
        out = open(os.path.join(base, f'{who}.out'), 'wb')
        err = open(os.path.join(base, f'{who}.err'), 'wb')
        p = subprocess.Popen(args, stdout=out, stderr=err, creationflags=creation)
        print(f'launched {who}  pid={p.pid}  -> {logs}')
    print('\n判分结束后：\n'
          '  主分        <task>/_rejudge/<执行体>/verifier/reward.json\n'
          '  逐条判分明细 <task>/_rejudge/<执行体>/verifier/reward-details.json\n'
          '注意：判分会把 __pycache__ 写进 tests/，打包前记得清理。')


if __name__ == '__main__':
    main()
