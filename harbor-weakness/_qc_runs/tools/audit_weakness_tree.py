# -*- coding: utf-8 -*-
"""盘点 harbor-weakness：题包本体、批次目录、zip 的对应关系与冗余，输出清理候选。

只读，不修改任何文件。
"""
import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")


def dsize(p: pathlib.Path):
    n = 0
    s = 0
    for q in p.rglob("*"):
        if q.is_file():
            n += 1
            try:
                s += q.stat().st_size
            except OSError:
                pass
    return n, s


def mb(x):
    return f"{x/1024/1024:.1f} MB"


def tree_sig(p: pathlib.Path, limit=4000):
    """目录内容指纹：相对路径 + 大小 + mtime 的滚动哈希（用于判重）。"""
    h = hashlib.sha256()
    cnt = 0
    for q in sorted(p.rglob("*")):
        if q.is_file():
            rel = q.relative_to(p).as_posix()
            st = q.stat()
            h.update(f"{rel}|{st.st_size}\n".encode())
            cnt += 1
            if cnt > limit:
                break
    return h.hexdigest()[:16], cnt


dirs, files = [], []
for e in W.iterdir():
    if e.name.startswith("."):
        continue
    (dirs if e.is_dir() else files).append(e)

print("=" * 100)
print("一、题包本体（FIN3-WKN-*）")
print("=" * 100)
for d in sorted([x for x in dirs if x.name.startswith("FIN3-WKN-")], key=lambda x: x.name):
    n, s = dsize(d)
    top = sorted(x.name for x in d.iterdir())[:10]
    print(f"  {d.name:<16} {n:>4} 文件 {mb(s):>9}   {top}")
    # 是否有判分产物
    rj = list(d.rglob("reward.json"))
    sub = [x.name for x in d.iterdir() if x.is_dir()]
    print(f"  {'':16} 子目录={sub}  内含 reward.json={len(rj)}")

print()
print("=" * 100)
print("二、批次目录（内容指纹判重）")
print("=" * 100)
batch = [x for x in dirs if x.name not in {"FIN3-WKN-148", "FIN3-WKN-149", "FIN3-WKN-150", "FIN3-WKN-151"}]
sigs = {}
for d in sorted(batch, key=lambda x: x.name):
    n, s = dsize(d)
    sig, cnt = tree_sig(d)
    sigs.setdefault(sig, []).append(d.name)
    task = [x.name for x in d.iterdir() if x.name.startswith("FIN3-WKN-")]
    print(f"  {d.name:<48} {n:>4} 文件 {mb(s):>9}  题={task} 指纹={sig}")

print()
print("  重复组（内容指纹相同，可能互为副本）:")
for sig, names in sigs.items():
    if len(names) > 1:
        print(f"    {sig} -> {names}")

print()
print("=" * 100)
print("三、zip 包")
print("=" * 100)
for f in sorted(files, key=lambda x: x.name):
    print(f"  {f.name:<48} {mb(f.stat().st_size):>9}  {f.stat().st_mtime}")

print()
print("=" * 100)
print("四、可清理候选（仅列出，不删除）")
print("=" * 100)
cands = []
for f in files:
    if f.suffix == ".zip":
        cands.append((f, f.stat().st_size, "历史版本 zip"))
for d in dirs:
    if d.name == "work_fin-b01_20261004_fix5":
        cands.append((d, dsize(d)[1], "空壳/近空目录"))
    if d.name == "_reference":
        cands.append((d, dsize(d)[1], "参考资料（非交付物）"))

for p, s, why in sorted(cands, key=lambda x: -x[1]):
    print(f"  [{why:<16}] {p.name:<46} {mb(s):>9}")
print()
print(f"  候选合计约 {mb(sum(c[1] for c in cands))}")
