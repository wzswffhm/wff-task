"""把经过净化的名称落到磁盘上。"""

import os

from .errors import InvalidNameError
from .rules import is_valid
from .sanitize import sanitize as _sanitize


class FileStore:
    """把名称映射到 ``root`` 目录下文件的简单存储。

    ``root`` 不存在时会被创建。同一个存储实例会记住已经写入过的名称，
    :meth:`list_names` 按写入顺序返回它们。
    """

    def __init__(self, root):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)
        self._names = []

    # -- 名称 ---------------------------------------------------------------

    def sanitize(self, name):
        """返回 ``name`` 在本存储中使用的落盘名称。"""
        return _sanitize(name)

    def target_path(self, name):
        """返回 ``name`` 对应的绝对路径（不检查该条目是否存在）。"""
        return os.path.join(self.root, self.sanitize(name))

    # -- 读写 ---------------------------------------------------------------

    def exists(self, name):
        """``name`` 对应的条目当前是否存在于磁盘上。"""
        return os.path.isfile(self.target_path(name))

    def save(self, name, data):
        """把 ``data``（bytes）写入 ``name`` 对应的文件，返回落盘名称。"""
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes-like")

        target = self.sanitize(name)

        if not is_valid(target):
            raise InvalidNameError("%r is not usable on Windows" % (target,))

        with open(os.path.join(self.root, target), "wb") as fh:
            fh.write(bytes(data))

        if target not in self._names:
            self._names.append(target)
        return target

    def load(self, name):
        """读回 ``name`` 对应的内容。"""
        with open(self.target_path(name), "rb") as fh:
            return fh.read()

    def list_names(self):
        """按写入顺序返回本存储已经写入过的名称。"""
        return list(self._names)

    def delete(self, name):
        """删除 ``name`` 对应的条目；条目不存在时返回 ``False``。"""
        path = self.target_path(name)
        if not os.path.isfile(path):
            return False
        os.remove(path)
        target = self.sanitize(name)
        if target in self._names:
            self._names.remove(target)
        return True
