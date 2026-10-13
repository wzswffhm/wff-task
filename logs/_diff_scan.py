import difflib, os, sys

base = r'C:\Users\Administrator\Desktop\wff-task\harbor-windows'
tasks = {
    '216': 'wfflab__wchunk-216-v1.2.0-delivery',
    '218': 'wfflab__wlogseg-218-v1.0.0-delivery',
    '219': 'wfflab__wpeimg-219-v1.0.0-delivery',
}
names = [
    'tests/run_tests.ps1',
    'tests/aggregate_results.ps1',
    'tests/test.ps1',
    'tests/test.bat',
    'environment/run.ps1',
    'environment/validate_environment.ps1',
    'environment/prepare.ps1',
    'environment/Dockerfile',
    'environment/agent_visible_paths.json',
    'environment/cleanup.ps1',
    'environment/restore.ps1',
    'solution/solve.ps1',
]
for name in names:
    print('#' * 30, name)
    contents = {}
    for k, t in tasks.items():
        p = os.path.join(base, t, name.replace('/', os.sep))
        contents[k] = open(p, encoding='utf-8', errors='replace').read().splitlines() if os.path.exists(p) else None
        print('  ', k, 'exists' if contents[k] is not None else 'MISSING',
              os.path.getsize(p) if os.path.exists(p) else '-')
    for pair in (('216', '218'), ('218', '219'), ('216', '219')):
        a, b = contents[pair[0]], contents[pair[1]]
        if a is None or b is None:
            continue
        d = list(difflib.unified_diff(a, b, fromfile=pair[0], tofile=pair[1], lineterm='', n=0))
        print('  --- diff %s->%s: %d lines' % (pair[0], pair[1], len(d)))
        for line in d[:80]:
            print('     ', line)
