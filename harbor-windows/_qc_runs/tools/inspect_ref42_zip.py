"""列出参考交付包 zip 的目录结构（只读，不解压）。"""
import sys
import zipfile
from collections import Counter, defaultdict

path = sys.argv[1]
with zipfile.ZipFile(path) as zf:
    names = [i.filename for i in zf.infolist() if not i.is_dir()]

print(f"total entries (files): {len(names)}")
print("top-level:", sorted({n.split('/')[0] for n in names}))

# 目录聚合
dirs = Counter()
examples = defaultdict(list)
for n in names:
    d = "/".join(n.split("/")[:-1]) or "."
    dirs[d] += 1
    if len(examples[d]) < 4:
        examples[d].append(n.split("/")[-1])

for d in sorted(dirs):
    print(f"\n[{d}]  ({dirs[d]} files)")
    for e in examples[d]:
        print("   -", e)

# 深度 <=2 的完整路径
print("\n=== paths depth<=3 ===")
for n in sorted(names):
    if n.count("/") <= 2:
        print(n)
