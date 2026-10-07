"""文件时间戳的读取与设置。"""

import os

from . import attributes
from .errors import WStampError

_FILE_ATTRIBUTE_READONLY = 0x01


def snapshot_times(path):
    """返回路径的时间戳快照。

    返回 dict：

    - ``mtime_ns``：修改时间（整数纳秒）。
    - ``atime_ns``：访问时间（整数纳秒）。
    - ``created``：文件创建时间。Windows 上 ``st_ctime`` 就是创建时间
      （birth time），这一点与 Linux（ctime = 元数据变更时间）不同。
    """
    st = os.stat(path)
    return {
        "mtime_ns": st.st_mtime_ns,
        "atime_ns": st.st_atime_ns,
        "created": st.st_ctime,
    }


def stamp_file(path, mtime_ns):
    """把 ``path`` 的 mtime 精确设置为整数纳秒 ``mtime_ns``。

    只修改 mtime，atime 保持原值。NTFS 以 100ns 为存储粒度，
    因此 ``mtime_ns`` 应当是 100 的倍数。

    目标带只读属性时不做任何写动作，抛出
    ``WStampError(kind="readonly")``。
    """
    st = os.stat(path)
    set_times(path, st.st_atime_ns, mtime_ns, restore_readonly=False)


def set_times(path, atime_ns, mtime_ns, restore_readonly=True):
    """同时设置 atime 与 mtime（整数纳秒）。

    ``restore_readonly=True`` 时，目标带只读属性则先清除属性、
    写完再恢复（供同步 / 复制流程使用）；为 ``False`` 时遇只读目标
    直接抛 ``WStampError(kind="readonly")``。
    """
    readonly_attrs = None
    if attributes.is_readonly(path):
        if not restore_readonly:
            raise WStampError("readonly", "%s is read-only" % path)
        readonly_attrs = attributes.get_attributes(path)
        attributes.set_attributes(path, readonly_attrs & ~_FILE_ATTRIBUTE_READONLY)
    try:
        os.utime(path, ns=(atime_ns, mtime_ns))
    finally:
        if readonly_attrs is not None:
            attributes.set_attributes(path, readonly_attrs)
