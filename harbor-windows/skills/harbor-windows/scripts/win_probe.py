# -*- coding: utf-8 -*-
"""win_probe.py —— 在本机真实 Windows 上实测改题将要依赖的文件系统语义。

改题要新增的 F2P 用例必须建立在**真实会被 Windows 拒绝**的操作上，否则
no-change 也能通过，就不是有效的 F2P。本脚本逐条验证假设。
"""

import os
import shutil
import stat
import sys
import tempfile

ROOT = os.path.join(tempfile.gettempdir(), "wff-winprobe")
if os.path.isdir(ROOT):
    shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(ROOT)

ok_count = 0
fail_count = 0


def case(name, fn):
    global ok_count, fail_count
    try:
        got = fn()
        print("  [%s] %s" % ("HIT " if got else "MISS", name))
        if got:
            ok_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print("  [ERR ] %s -> %s: %s" % (name, type(e).__name__, str(e)[:160]))
        fail_count += 1


def winerr(e):
    return getattr(e, "winerror", None)


print("=" * 72)
print("Windows 文件系统语义实测（Python %s, os.name=%s）" % (sys.version.split()[0], os.name))
print("=" * 72)

# ---------------------------------------------------------------- 1
def t1():
    """只读文件 os.remove -> PermissionError(WinError 5)"""
    p = os.path.join(ROOT, "ro1.txt")
    open(p, "w").write("x")
    os.chmod(p, os.stat(p).st_mode & ~stat.S_IWRITE)
    try:
        os.remove(p)
        return False
    except PermissionError as e:
        print("      winerror=%s" % winerr(e))
        return True


# ---------------------------------------------------------------- 2
def t2():
    """只读目录是否挡住其中的子文件删除"""
    d = os.path.join(ROOT, "rodir1")
    os.makedirs(d)
    f = os.path.join(d, "child.txt")
    open(f, "w").write("x")
    os.chmod(d, os.stat(d).st_mode & ~stat.S_IWRITE)
    try:
        os.remove(f)
        return False
    except PermissionError as e:
        print("      winerror=%s" % winerr(e))
        return True


# ---------------------------------------------------------------- 3
def t3():
    """只读空目录 os.rmdir -> PermissionError?"""
    d = os.path.join(ROOT, "rodir2")
    os.makedirs(d)
    os.chmod(d, os.stat(d).st_mode & ~stat.S_IWRITE)
    try:
        os.rmdir(d)
        return False
    except PermissionError as e:
        print("      winerror=%s" % winerr(e))
        return True


# ---------------------------------------------------------------- 4
def t4():
    """只读文件被占用时，清掉只读属性后再删是否仍失败（WinError 32）"""
    p = os.path.join(ROOT, "rolock.txt")
    open(p, "w").write("x")
    os.chmod(p, os.stat(p).st_mode & ~stat.S_IWRITE)
    h = open(p, "r")
    try:
        try:
            os.remove(p)
            return False
        except PermissionError as e1:
            w1 = winerr(e1)
            os.chmod(p, os.stat(p).st_mode | stat.S_IWRITE)   # 清只读
            try:
                os.remove(p)
                return False
            except PermissionError as e2:
                print("      first=%s after_make_writable=%s" % (w1, winerr(e2)))
                return True
    finally:
        h.close()


# ---------------------------------------------------------------- 5
def t5():
    """打开句柄占用：os.remove -> PermissionError(WinError 32)"""
    p = os.path.join(ROOT, "lock.txt")
    open(p, "w").write("x")
    h = open(p, "r")
    try:
        try:
            os.remove(p)
            return False
        except PermissionError as e:
            print("      winerror=%s" % winerr(e))
            return True
    finally:
        h.close()


# ---------------------------------------------------------------- 6
def t6():
    """目标是目录时以 'wb' 打开 -> 报错"""
    d = os.path.join(ROOT, "isdir")
    os.makedirs(d)
    try:
        open(d, "wb")
        return False
    except (PermissionError, IsADirectoryError, OSError) as e:
        print("      %s winerror=%s" % (type(e).__name__, winerr(e)))
        return True


# ---------------------------------------------------------------- 7
def t7():
    """父路径上存在同名**文件**时 os.makedirs -> 报错"""
    base = os.path.join(ROOT, "conflict")
    os.makedirs(base)
    open(os.path.join(base, "data"), "w").write("file")   # data 是文件
    try:
        os.makedirs(os.path.join(base, "DATA"))          # 想建同名目录（仅大小写不同）
        return False
    except (FileExistsError, NotADirectoryError, OSError) as e:
        print("      %s winerror=%s" % (type(e).__name__, winerr(e)))
        return True


# ---------------------------------------------------------------- 8
def t8():
    """父路径上存在同名**目录**时用 'wb' 打开其同名子路径 -> 报错"""
    base = os.path.join(ROOT, "conflict2")
    os.makedirs(os.path.join(base, "a", "b"))            # a/b 是目录
    try:
        open(os.path.join(base, "a", "b"), "wb")         # 想写同名文件
        return False
    except (PermissionError, IsADirectoryError, OSError) as e:
        print("      %s winerror=%s" % (type(e).__name__, winerr(e)))
        return True


# ---------------------------------------------------------------- 9
def t9():
    """清掉只读属性的**目录**能否被 rmdir（验证修复路径可行）"""
    d = os.path.join(ROOT, "rodir3")
    os.makedirs(d)
    os.chmod(d, os.stat(d).st_mode & ~stat.S_IWRITE)
    os.chmod(d, os.stat(d).st_mode | stat.S_IWRITE)
    try:
        os.rmdir(d)
        return True
    except PermissionError:
        return False


# ---------------------------------------------------------------- 10
def t10():
    """目录只读属性在 Windows 上是否真的被写入（stat 可读回）"""
    d = os.path.join(ROOT, "rodir4")
    os.makedirs(d)
    os.chmod(d, os.stat(d).st_mode & ~stat.S_IWRITE)
    return not bool(os.stat(d).st_mode & stat.S_IWRITE)


# ---------------------------------------------------------------- 11
def t11():
    """对文件 os.utime 设 mtime：能否把目标 mtime 改成与源一致"""
    a = os.path.join(ROOT, "m_a.txt")
    b = os.path.join(ROOT, "m_b.txt")
    open(a, "w").write("same")
    open(b, "w").write("same")
    os.utime(a, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    shutil.copyfile(a, b)
    return os.stat(b).st_mtime_ns != os.stat(a).st_mtime_ns   # copyfile 不保留 mtime


# ---------------------------------------------------------------- 12
def t12():
    """shutil.rmtree 遇只读子文件是否失败（onerror 是否被触发）"""
    d = os.path.join(ROOT, "tree_ro")
    os.makedirs(d)
    f = os.path.join(d, "ro.bin")
    open(f, "w").write("x")
    os.chmod(f, os.stat(f).st_mode & ~stat.S_IWRITE)
    try:
        shutil.rmtree(d)
        return False
    except PermissionError:
        return True


for i, fn in enumerate([t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12], 1):
    case("t%02d" % i, fn)

print("-" * 72)
print("可用（会失败/报错）= %d   不可用 = %d" % (ok_count, fail_count))
print("ROOT = %s" % ROOT)
