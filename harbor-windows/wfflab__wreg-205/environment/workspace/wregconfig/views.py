"""注册表视图。

在 64 位 Windows 上，注册表的 ``SOFTWARE`` 键被分成两个视图：64 位视图和
32 位视图（后者物理上落在 ``Wow6432Node`` 之下）。32 位程序看到的
``HKLM\\SOFTWARE\\Vendor`` 与 64 位程序看到的同名键，其实是两个不同的键。
访问时可以显式要求某一个视图，也可以使用进程默认视图。
"""

import winreg

#: 支持的视图名称。
VIEWS = ("default", "64", "32")


def view_flags(view):
    """返回访问注册表时应当附加的 WOW64 标志。

    64 位进程中，``"64"`` 与 ``"default"`` 指向同一个视图，
    因此只有前者需要显式标志。
    """
    if view == "64":
        return winreg.KEY_WOW64_64KEY
    return 0


def view_description(view):
    """返回视图的可读说明。"""
    if view == "32":
        return "32-bit view (Wow6432Node)"
    if view == "64":
        return "64-bit view"
    return "process default view"
