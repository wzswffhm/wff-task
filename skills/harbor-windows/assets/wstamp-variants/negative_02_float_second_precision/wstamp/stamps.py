"""时间戳设置（反例：float 秒精度，纳秒信息在换算中丢失）。"""

import os

from . import attributes
from .errors import WStampError

_FILE_ATTRIBUTE_READONLY = 0x01


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
    """反例实现：把纳秒换算成 float 秒交给 os.utime，精度只有 ~0.5 微秒。"""
    readonly_attrs = None
    if attributes.is_readonly(path):
        if not restore_readonly:
            raise WStampError("readonly", "%s is read-only" % path)
        readonly_attrs = attributes.get_attributes(path)
        attributes.set_attributes(path, readonly_attrs & ~_FILE_ATTRIBUTE_READONLY)
    try:
        os.utime(path, (atime_ns / 1e9, mtime_ns / 1e9))
    finally:
        if readonly_attrs is not None:
            attributes.set_attributes(path, readonly_attrs)
