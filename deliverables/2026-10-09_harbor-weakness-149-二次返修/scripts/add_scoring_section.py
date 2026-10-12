# -*- coding: utf-8 -*-
"""按 2026-10-10 质检报告(2) 项7：为 tests/rubrics.toml 补 [scoring] aggregation = "weighted_mean"。
保持原行尾（CRLF/LF）不变。
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                 r'\FIN3-WKN-149\tests\rubrics.toml')
raw = P.read_bytes()
t = raw.decode('utf-8')
nl = '\r\n' if '\r\n' in t else '\n'
print(f'文件 {P.name}: {len(raw):,} B  行尾={"CRLF" if nl == chr(13) + chr(10) else "LF"}  '
      f'已含 [scoring]={"[scoring]" in t}')
if '[scoring]' in t:
    print('无需修改')
else:
    if not t.endswith(nl):
        t += nl
    t += nl + '[scoring]' + nl + 'aggregation = "weighted_mean"' + nl
    P.write_bytes(t.encode('utf-8'))
    print(f'[OK] 已追加 [scoring] 段，新大小 {P.stat().st_size:,} B')

t2 = P.read_bytes().decode('utf-8')
print('\n=== 末尾 6 行 ===')
for ln in t2.splitlines()[-6:]:
    print('  ', ln)
print(f'\n[校验] [scoring] 出现 {t2.count("[scoring]")} 次；'
      f'aggregation 出现 {t2.count("aggregation")} 次；'
      f'criterion 数 {t2.count("[[criterion]]")}')
try:
    import tomllib
    d = tomllib.loads(t2)
    print(f'[校验] TOML 解析 OK；scoring={d.get("scoring")}；criterion 数={len(d.get("criterion", []))}')
except Exception as e:  # noqa: BLE001
    print(f'[ERR] TOML 解析失败: {e}')
