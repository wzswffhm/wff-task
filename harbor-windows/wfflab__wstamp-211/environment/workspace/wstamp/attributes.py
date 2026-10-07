"""文件属性（只读 / 隐藏）的读取与设置。

Windows 的文件属性不走 POSIX 权限位，只能通过 Win32 的
``GetFileAttributesW`` / ``SetFileAttributesW`` 读取与设置。
"""

import ctypes

_FILE_ATTRIBUTE_READONLY = 0x01
_FILE_ATTRIBUTE_HIDDEN = 0x02

_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF


def get_attributes(path):
    """返回 ``GetFileAttributesW`` 的原始属性位。"""
    value = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if value == _INVALID_FILE_ATTRIBUTES:
        raise ctypes.WinError()
    return value


def is_readonly(path):
    """路径是否带只读属性。"""
    return bool(get_attributes(path) & _FILE_ATTRIBUTE_READONLY)


def is_hidden(path):
    """路径是否带隐藏属性。"""
    return bool(get_attributes(path) & _FILE_ATTRIBUTE_HIDDEN)


def set_attributes(path, attrs):
    """把路径的属性位整体设置为 ``attrs``。"""
    if not ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs):
        raise ctypes.WinError()
