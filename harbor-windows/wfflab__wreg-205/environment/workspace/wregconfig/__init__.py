"""wregconfig —— 在 Windows 注册表里读写应用配置。

同一份配置在 32 位与 64 位程序眼里可能是两个不同的键：注册表的 ``SOFTWARE``
子树按视图分开存放。工具必须能显式选择视图，才能读到老版本程序写下的配置。
"""

from .errors import ConfigError, WRegError
from .store import ConfigStore
from .views import VIEWS, view_description, view_flags

__version__ = "2.4.0"

__all__ = [
    "ConfigError",
    "ConfigStore",
    "VIEWS",
    "WRegError",
    "view_description",
    "view_flags",
]
