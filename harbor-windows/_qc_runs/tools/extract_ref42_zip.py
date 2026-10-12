"""解压参考交付包到目标目录（只读参考，不复用它做交付）。"""
import sys
import zipfile
from pathlib import Path

src, dst = sys.argv[1], Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(src) as zf:
    zf.extractall(dst)
print(f"extracted {src} -> {dst}")
for p in sorted(dst.rglob("*")):
    if p.is_file():
        print(f"{p.stat().st_size:>10}  {p.relative_to(dst).as_posix()}")
