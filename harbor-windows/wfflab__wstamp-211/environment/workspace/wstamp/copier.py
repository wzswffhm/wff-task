"""单文件复制与时间戳 / 属性搬运。"""

import os
import shutil


def copy_stamp(src, dst):
    """复制单个文件，把源的时间戳尽量带过去。

    目前先用 ``copyfile`` 落盘，再把源的 mtime（秒）设到目标上。
    """
    shutil.copyfile(src, dst)
    st = os.stat(src)
    os.utime(dst, (st.st_mtime, st.st_mtime))
