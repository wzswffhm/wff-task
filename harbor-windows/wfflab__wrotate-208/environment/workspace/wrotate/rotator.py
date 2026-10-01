"""日志轮转。

按序号滚动日志文件：``app.log`` → ``app.log.1`` → ``app.log.2`` ……，
并按保留份数把最老的那些删掉。
"""

import os

from . import fsutil
from .errors import RotationError


class Rotator(object):
    """一个日志文件的轮转器。"""

    def __init__(self, path, keep=5):
        self.path = os.path.abspath(path)
        self.keep = int(keep)

    @property
    def directory(self):
        return os.path.dirname(self.path)

    @property
    def stem(self):
        return os.path.basename(self.path)

    def rotations(self):
        """返回当前存在的轮转文件名（按序号升序）。"""
        return fsutil.rotation_names(self.directory, self.stem)

    def rotate(self):
        """把当前日志滚成 ``.1``，并把已有轮转依次后移。

        返回本次被写入的新路径列表。
        """
        if not os.path.exists(self.path):
            return []

        moved = []
        for name in self.rotations():
            index = fsutil.rotation_index(name)
            src = os.path.join(self.directory, name)
            dst = "%s.%d" % (self.path, index + 1)
            fsutil.move(src, dst)
            moved.append(dst)

        dst = "%s.1" % self.path
        fsutil.move(self.path, dst)
        moved.append(dst)
        return moved

    def prune(self):
        """删除超出保留份数的轮转文件，返回被删除的名字列表。"""
        names = self.rotations()
        ordered = sorted(names, reverse=True)
        removed = []
        for name in ordered[self.keep:]:
            if fsutil.remove(os.path.join(self.directory, name)):
                removed.append(name)
        return removed

    def rotate_and_prune(self):
        """轮转并立刻整理保留份数。"""
        moved = self.rotate()
        if not moved:
            raise RotationError("nothing to rotate: %s" % self.path)
        self.prune()
        return moved
