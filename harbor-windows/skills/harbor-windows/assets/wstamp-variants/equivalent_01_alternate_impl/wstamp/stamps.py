"""时间戳设置（等价实现：清除只读用 os.chmod，属性位判定仍走 Win32）。"""

import os
import stat

from . import attributes
from .errors import WStampError


def snapshot_times(path):
    st = os.stat(path)
    return {
        "mtime_ns": st.st_mtime_ns,
        "atime_ns": st.st_atime_ns,
        "created": st.st_ctime,
    }


def stamp_file(path, mtime_ns):
    st = os.stat(path)
    set_times(path, st.st_atime_ns, mtime_ns, restore_readonly=False)


def set_times(path, atime_ns, mtime_ns, restore_readonly=True):
    """只读目标：os.chmod(S_IWRITE) 解除写保护，写完恢复 S_IREAD。

    CPython 的 os.chmod 在 Windows 上只增删 FILE_ATTRIBUTE_READONLY 位，
    不影响隐藏等其他属性位，与「清属性→写→恢复」语义等价。
    """
    cleared = False
    if attributes.is_readonly(path):
        if not restore_readonly:
            raise WStampError("readonly", "%s is read-only" % path)
        os.chmod(path, stat.S_IWRITE)
        cleared = True
    try:
        os.utime(path, ns=(atime_ns, mtime_ns))
    finally:
        if cleared:
            os.chmod(path, stat.S_IREAD)
