"""文本编码的选择。

同一个字节能表示什么，完全取决于用什么编码去解。Windows 的「系统默认编码」
是当前 ANSI 代码页（英文系统上通常是 cp1252），而 Linux 上是 UTF-8；
同一个程序在两个平台上按默认值写文件，落盘的字节并不一样。
所以对需要跨平台交换的文本，必须显式选定编码。
"""

import locale

#: 本库在「默认」情形下应当使用的编码。
DEFAULT_ENCODING = "utf-8"

#: 带字节序标记的 UTF-8。
BOM_ENCODING = "utf-8-sig"

#: 编码别名到 ``open()`` 可接受名称的映射。
ALIASES = {
    "default": None,
    "utf8": None,
    "utf-8": None,
    "utf-8-bom": "utf-8",
    "utf-8-sig": "utf-8",
    "ansi": "mbcs",
    "latin-1": "latin-1",
    "cp1252": "cp1252",
}


def system_encoding():
    """返回当前平台的系统默认文本编码。"""
    return locale.getpreferredencoding(False)


def encoding_for(name):
    """返回写读文件时应当交给 ``open()`` 的编码名。

    ``None`` 表示交给 ``open()`` 使用平台默认值。
    """
    key = (name or "default").lower()
    if key in ALIASES:
        return ALIASES[key]
    return name


def known_encodings():
    """返回受支持的编码别名。"""
    return sorted(ALIASES)
