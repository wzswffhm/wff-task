"""单文件复制（反例：不搬运只读/隐藏属性，其余用纳秒精确实现）。"""

import os
import shutil

from .stamps import set_times


def copy_stamp(src, dst):
    """反例：时间戳逐纳秒带过去，但属性位不搬运。"""
    st = os.stat(src)
    shutil.copyfile(src, dst)
    set_times(dst, st.st_atime_ns, st.st_mtime_ns, restore_readonly=True)
