# -*- coding: utf-8 -*-
"""同步修复后的金标产物：solution/golden_output 与 tests/__golden_output 各自重跑一遍，校验逐字节一致。"""
import hashlib
import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
PKG = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
SOL = PKG / 'solution' / 'golden_output'
TST = PKG / 'tests' / '__golden_output'
INP = PKG / 'environment' / 'input_files'
PY = r'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
TMP = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                   r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2\sync')

ONLY_SCRIPT = ['FIN3-WKN-149_reproduce.py']          # 只有脚本改动时可选
ALL7 = ['FIN3-WKN-149_reproduce.py',
        'FIN3-WKN-149_风险委员会决策备忘录.md',
        'FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png',
        'FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png',
        'FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png',
        'FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png',
        'FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def run_to(outdir):
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    p = subprocess.run([PY, str(SOL / 'FIN3-WKN-149_reproduce.py'), str(INP), str(outdir)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stderr or '')[-200:]


print('=== 步骤1：用修复后脚本生成到 TMP ===')
rc, err = run_to(TMP)
print(f'  rc={rc} {err}')
assert rc == 0, '金标重跑失败'

# 备忘录与图是脚本自动生成的；脚本本身需原样复制
targets = [SOL, TST]
print('\n=== 步骤2：写入两份 golden_output ===')
# 脚本本身已在 SOL，不自复制；TMP 只产出备忘录+5图，从 TMP 拷到两处
for d in targets:
    for rel in ALL7:
        src = SOL / rel if rel.endswith('reproduce.py') else TMP / rel
        dst = d / rel
        if src.resolve() == dst.resolve():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    print(f'  {d}: 已写 {len(ALL7)} 文件')

print('\n=== 步骤3：两份逐字节校验 ===')
same = True
for rel in ALL7:
    a, b = SOL / rel, TST / rel
    ha, hb = sha(a), sha(b)
    ok = ha == hb and a.stat().st_size == b.stat().st_size
    same &= ok
    print(f'  {"OK" if ok else "DIFF"} {rel.split("/")[-1]:44s} sol={ha} tst={hb} '
          f'{a.stat().st_size}B')

# 备忘录关键数值核对
memo = (SOL / 'FIN3-WKN-149_风险委员会决策备忘录.md').read_text(encoding='utf-8')
print('\n=== 备忘录关键数值 ===')
for pat in ['5.05', '5.045', '7.03', '7.030', '9.90', '9.902', '8.916', '6.650',
            '5.564', '5.565', '7.455', '1.72%', '0.0172']:
    print(f'  含「{pat}」: {pat in memo}')
print(f'  备忘录行数: {len(memo.splitlines())}')
print(f'\n结论: {"两份 golden_output 完全一致" if same else "存在差异，需排查"}')
sys.exit(0 if same else 1)
