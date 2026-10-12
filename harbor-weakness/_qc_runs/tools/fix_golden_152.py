# -*- coding: utf-8 -*-
"""修复 152 golden 三处不一致：
现状:
  solution/golden_output    == tests/__golden_output__  （v3 正确金标，= v3 oracle output）
  tests/__golden_output     = 旧版残留（3 文件不同），但它是平台/质检口径的标准目录名
动作:
  1) 旧 tests/__golden_output 先备份到 _backup
  2) solution/golden_output -> tests/__golden_output （逐字节复制）
  3) 删除违规残留目录 tests/__golden_output__（结尾双下划线）
  4) 验证三处（应为两处）逐字节一致
"""
import hashlib
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = W / "harbor-weakness" / "FIN3-WKN-152"
SOL = TASK / "solution" / "golden_output"
T1 = TASK / "tests" / "__golden_output"
T2 = TASK / "tests" / "__golden_output__"
BK = W / "harbor-weakness" / "_backup" / "FIN3-WKN-152-golden-old-20261010"

DRY = len(sys.argv) > 1 and sys.argv[1] == "--dry-run"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def files(d):
    return {p.name: p for p in d.iterdir() if p.is_file()}


print("=" * 100)
print("前置校验")
print("=" * 100)
for p in (SOL, T1, T2):
    assert p.is_dir(), f"缺目录 {p}"
    print(f"  [OK] {p}  {len(files(p))} 文件")

# 断言：solution 与 __golden_output__ 完全一致（说明后者才是现行金标）
sol = files(SOL)
g2 = files(T2)
g1 = files(T1)
assert set(sol) == set(g2), f"文件名集合不同 {set(sol) ^ set(g2)}"
diff2 = [n for n in sol if sha(sol[n]) != sha(g2[n])]
diff1 = [n for n in sol if sha(sol[n]) != sha(g1[n])]
print(f"  solution vs __golden_output__: 差异 {len(diff2)} 个 {diff2}")
print(f"  solution vs __golden_output : 差异 {len(diff1)} 个 {diff1}")
assert not diff2, f"solution 与 __golden_output__ 不一致，不能作为复制源: {diff2}"

# 断言：旧 __golden_output 确实是旧版（与 v3 oracle output 不同）
ORACLE = W / "harbor-weakness" / "_qc_runs" / "g4-152v3" / "trials" / "oracle-152v3" / "artifacts" / "app" / "output"
if ORACLE.is_dir():
    of = files(ORACLE)
    d_o = [n for n in g1 if n in of and sha(g1[n]) != sha(of[n])]
    print(f"  v3 oracle output vs 旧 __golden_output: 差异 {len(d_o)} 个 {d_o}")

# 安全断言：目标路径必须在题包 tests 下
for p in (T1, T2, BK):
    assert "FIN3-WKN-152" in str(p) or "_backup" in str(p), f"异常路径 {p}"
    print(f"  路径核对 OK: {p}")

if DRY:
    print("\n--dry-run：不执行任何修改")
    sys.exit(0)

print()
print("=" * 100)
print("执行")
print("=" * 100)

# 1) 备份旧 tests/__golden_output
if BK.exists():
    shutil.rmtree(BK)
BK.mkdir(parents=True)
for n, p in files(T1).items():
    shutil.copy2(p, BK / n)
print(f"  [1] 旧 tests/__golden_output 已备份 -> {BK} ({len(files(BK))} 文件)")

# 2) solution -> tests/__golden_output
for n, p in files(SOL).items():
    shutil.copy2(p, T1 / n)
print(f"  [2] solution/golden_output 已复制到 tests/__golden_output ({len(files(T1))} 文件)")

# 3) 删除违规残留目录
shutil.rmtree(T2)
print(f"  [3] 已删除残留目录 {T2}")

# 4) 验证
a, b = files(SOL), files(T1)
assert set(a) == set(b), "文件名不一致"
bad = [n for n in a if sha(a[n]) != sha(b[n])]
assert not bad, f"仍不一致 {bad}"
print(f"  [4] 验证通过：solution/golden_output == tests/__golden_output（{len(a)} 文件逐字节一致）")
print(f"      残留目录存在？{T2.exists()}（应为 False）")

# 5) 确认 tests 下只有标准目录
tests = TASK / "tests"
gd = [p.name for p in tests.iterdir() if p.is_dir() and "golden" in p.name]
print(f"  [5] tests 下 golden 目录: {gd}")
assert gd == ["__golden_output"], f"异常: {gd}"

print()
print(">>> 修复完成")
