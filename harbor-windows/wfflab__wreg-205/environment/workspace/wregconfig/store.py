"""把某个注册表路径当作一个配置节来读写。"""

import winreg

from .errors import ConfigError
from .views import VIEWS, view_flags

_MISSING = object()


class ConfigStore(object):
    """某个注册表路径下的配置节。

    ``view`` 取 ``"default"`` / ``"64"`` / ``"32"``，决定访问哪一个注册表视图。
    """

    def __init__(self, hive, path, view="default"):
        if view not in VIEWS:
            raise ValueError("unknown view: %r" % (view,))
        self.hive = hive
        self.path = path
        self.view = view

    # -- 内部 ---------------------------------------------------------------

    @property
    def flags(self):
        return view_flags(self.view)

    def _open(self, access):
        return winreg.OpenKey(self.hive, self.path, 0, access | self.flags)

    def _create(self, access):
        return winreg.CreateKeyEx(self.hive, self.path, 0, access | self.flags)

    def child(self, name):
        """返回本节的子节。"""
        return ConfigStore(self.hive, "%s\\%s" % (self.path, name), self.view)

    # -- 查询 ---------------------------------------------------------------

    def exists(self):
        """配置节当前是否存在（在所选视图内）。"""
        try:
            with self._open(winreg.KEY_READ):
                return True
        except FileNotFoundError:
            return False

    def names(self):
        """返回本节下的值名列表。"""
        try:
            with self._open(winreg.KEY_READ) as key:
                count = winreg.QueryInfoKey(key)[1]
                return [winreg.EnumValue(key, i)[0] for i in range(count)]
        except FileNotFoundError:
            return []

    def read(self, name, default=_MISSING):
        """读取一个值；缺失时返回 ``default`` 或抛 :class:`ConfigError`。"""
        try:
            with self._open(winreg.KEY_READ) as key:
                value, _kind = winreg.QueryValueEx(key, name)
                return value
        except FileNotFoundError:
            if default is _MISSING:
                raise ConfigError("missing value %r in %s" % (name, self.path))
            return default

    # -- 修改 ---------------------------------------------------------------

    def write(self, name, value):
        """写入一个字符串值。"""
        with self._create(winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))

    def delete(self, name):
        """删除一个值；值不存在时返回 ``False``。"""
        try:
            with self._open(winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, name)
                return True
        except FileNotFoundError:
            return False

    def delete_tree(self):
        """删除整个配置节。"""
        winreg.DeleteKey(self.hive, self.path)
