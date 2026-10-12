#!/usr/bin/env python
"""Windows 安装事务语义探针（先实测，后出题）。

要回答的问题：winstall 依赖的「目标文件被其它进程打开 → 无法替换」这条
Windows 语义在什么条件下成立？「不可延迟的硬失败」又怎样与它区分开？
"""

import os
import shutil
import sys
import tempfile

SCRATCH = tempfile.mkdtemp(prefix="winstall-probe-")
RESULTS = []


def make_src(d, marker):
    src = os.path.join(d, "src.bin")
    with open(src, "wb") as fh:
        fh.write(marker)
    return src


def atomic_put(src, dst):
    """与 winstall._put_file 相同的手法：同目录临时文件 + 原子替换。"""
    tmp = dst + ".winstall-part"
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def c1_locked_target_blocks_atomic_replace(d):
    """目标文件被另一个只读句柄打开时，原子替换是否失败？"""
    src = make_src(d, b"new")
    dst = os.path.join(d, "target.dll")
    with open(dst, "wb") as fh:
        fh.write(b"old")
    with open(dst, "rb"):
        try:
            atomic_put(src, dst)
        except OSError as e:
            return True, "%s winerror=%s errno=%s" % (type(e).__name__,
                                                      getattr(e, "winerror", None), e.errno)
    return False, "替换竟然成功：只读句柄未能阻止替换"


def c2_copyfile_ignores_reader(d):
    """对照：普通 copyfile 是否被只读句柄挡住？"""
    src = make_src(d, b"new")
    dst = os.path.join(d, "target.dll")
    with open(dst, "wb") as fh:
        fh.write(b"old")
    with open(dst, "rb"):
        try:
            shutil.copyfile(src, dst)
        except OSError as e:
            return False, "copyfile 也被挡住：%s winerror=%s" % (type(e).__name__,
                                                                getattr(e, "winerror", None))
    return True, "copyfile 成功 → 必须用原子替换才能暴露「被占用」"


def c3_replace_works_after_release(d):
    """句柄释放后原子替换必须成功（「下一次执行完成替换」的前提）。"""
    src = make_src(d, b"new")
    dst = os.path.join(d, "target.dll")
    with open(dst, "wb") as fh:
        fh.write(b"old")
    holder = open(dst, "rb")
    try:
        atomic_put(src, dst)
    except OSError:
        pass
    holder.close()
    try:
        atomic_put(src, dst)
    except OSError as e:
        return False, "释放后仍失败：%s winerror=%s" % (type(e).__name__, getattr(e, "winerror", None))
    with open(dst, "rb") as fh:
        return fh.read() == b"new", "内容=%r" % (open(dst, "rb").read(),)


def c4_locked_target_keeps_old_content(d):
    """替换失败后目标文件是否仍是旧内容，是否留下临时文件？"""
    src = make_src(d, b"new")
    dst = os.path.join(d, "target.dll")
    with open(dst, "wb") as fh:
        fh.write(b"old")
    with open(dst, "rb"):
        try:
            atomic_put(src, dst)
        except OSError:
            pass
    with open(dst, "rb") as fh:
        body = fh.read()
    leftover = sorted(n for n in os.listdir(d) if n.endswith(".winstall-part"))
    return body == b"old", "内容=%r 残留=%s" % (body, leftover)


def c5_directory_at_target_is_distinguishable(d):
    """目标位置是目录时的失败码与「被占用」是否可区分？"""
    src = make_src(d, b"new")
    dst = os.path.join(d, "blocked.dat")
    os.makedirs(dst, exist_ok=True)
    try:
        atomic_put(src, dst)
    except OSError as e:
        return True, "%s winerror=%s errno=%s isdir(dst)=%s" % (
            type(e).__name__, getattr(e, "winerror", None), e.errno, os.path.isdir(dst))
    return False, "竟然成功"


def c6_winerror_numbers(d):
    """把三个相关 WinError 码的数值确认一遍。"""
    src = make_src(d, b"new")
    dst = os.path.join(d, "target.dll")
    with open(dst, "wb") as fh:
        fh.write(b"old")
    lock_err = None
    with open(dst, "rb"):
        try:
            atomic_put(src, dst)
        except OSError as e:
            lock_err = getattr(e, "winerror", None)
    hard_err = None
    bad = os.path.join(d, "blocked.dat")
    os.makedirs(bad, exist_ok=True)
    try:
        atomic_put(src, bad)
    except OSError as e:
        hard_err = getattr(e, "winerror", None)
    return (lock_err is not None and hard_err is not None and lock_err != hard_err), \
        "被占用 winerror=%s / 目标是目录 winerror=%s" % (lock_err, hard_err)


CASES = [
    ("c1_locked_target_blocks_atomic_replace", c1_locked_target_blocks_atomic_replace),
    ("c2_copyfile_ignores_reader", c2_copyfile_ignores_reader),
    ("c3_replace_works_after_release", c3_replace_works_after_release),
    ("c4_locked_target_keeps_old_content", c4_locked_target_keeps_old_content),
    ("c5_directory_at_target_is_distinguishable", c5_directory_at_target_is_distinguishable),
    ("c6_winerror_numbers", c6_winerror_numbers),
]


def main():
    print("Python: %s | os.name = %s" % (sys.version.split()[0], os.name), flush=True)
    print("=" * 96, flush=True)
    for name, fn in CASES:
        d = os.path.join(SCRATCH, name)
        os.makedirs(d, exist_ok=True)
        try:
            ok, detail = fn(d)
        except Exception as e:  # noqa: BLE001
            ok, detail = False, "%s: %s" % (type(e).__name__, e)
        RESULTS.append((name, ok, detail))
        print("%-46s %s  %s" % (name, "HIT " if ok else "MISS", detail), flush=True)
    print("=" * 96, flush=True)
    print("命中 %d / %d" % (sum(1 for _, ok, _ in RESULTS if ok), len(RESULTS)))
    print("临时目录保留在:", SCRATCH)


if __name__ == "__main__":
    main()
