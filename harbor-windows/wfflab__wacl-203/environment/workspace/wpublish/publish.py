"""把构建产物发布到共享目录。"""

import os
import shutil

from .icacls import deny, list_aces, list_explicit_aces
from .rights import can_write

#: 只读发布时授给访问者的权限（对象继承 + 容器继承 + 读取执行）。
READONLY_SPEC = "(OI)(CI)(RX)"


def publish(src_dir, dst_dir, principal):
    """把 ``src_dir`` 发布到 ``dst_dir``。

    目标目录会被创建；``principal`` 在整个子树内只读。
    返回已发布的根目录。
    """
    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
    deny(dst_dir, principal, READONLY_SPEC)
    return dst_dir


def audit(dst_dir, principal):
    """返回 ``dst_dir`` 子树内 ``principal`` 仍可写入的路径列表。"""
    offenders = []
    for dirpath, dirnames, filenames in os.walk(dst_dir):
        for name in list(dirnames) + list(filenames):
            path = os.path.join(dirpath, name)
            if can_write(path, principal):
                offenders.append(path)
    return sorted(offenders)


def explicit_grants(path):
    """返回 ``path`` 上显式设置的允许项主体集合。"""
    return sorted({a.principal for a in list_explicit_aces(path) if not a.deny})


def all_principals(path):
    """返回 ``path`` 上出现过的全部主体。"""
    return sorted({a.principal for a in list_aces(path)})
