"""文件系统操作的薄封装。

这里的每个函数都要求「目标已经存在时也要成功」：日志轮转本质上是把一个
序号文件搬到下一个序号上，而下一个序号上往往已经有上一轮留下的残留。
"""

import os


def move(src, dst):
    """把 ``src`` 移动到 ``dst``。

    目标已存在时也应当成功（覆盖它），返回 ``dst``。
    """
    os.rename(src, dst)
    return dst


def remove(path):
    """删除一个文件；不存在时返回 ``False``。"""
    try:
        os.remove(path)
    except FileNotFoundError:
        return False
    return True


def rotation_names(directory, stem):
    """返回 ``directory`` 中形如 ``stem.<n>`` 的名字列表（升序）。"""
    names = []
    for name in os.listdir(directory):
        if not name.startswith(stem + "."):
            continue
        suffix = name[len(stem) + 1:]
        if suffix.isdigit():
            names.append(name)
    return sorted(names)


def rotation_index(name):
    """返回轮转文件名的序号。"""
    return int(name.rsplit(".", 1)[1])
