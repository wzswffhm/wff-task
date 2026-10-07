"""单文件复制（等价实现：显式字节流代替 shutil.copyfile）。"""

import os

from . import attributes
from .stamps import set_times


def copy_stamp(src, dst):
    """先取源快照，再以字节流落盘，最后时间戳 + 属性位一次到位。"""
    st = os.stat(src)
    attrs = attributes.get_attributes(src)
    with open(src, "rb") as fh:
        data = fh.read()
    with open(dst, "wb") as fh:
        fh.write(data)
    set_times(dst, st.st_atime_ns, st.st_mtime_ns, restore_readonly=True)
    attributes.set_attributes(dst, attrs)
