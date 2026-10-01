"""Windows 目标文件系统上的名称规则。

这里集中放置「某个名称能不能直接在 Windows 上作为文件条目使用」的判断，
以及净化名称时需要用到的常量。
"""

#: Win32 保留设备名。
RESERVED_BASE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + ["COM%d" % i for i in range(1, 10)]
    + ["LPT%d" % i for i in range(1, 10)]
)

#: 在 Win32 路径中必须替换掉的字符。
ILLEGAL_CHARS = frozenset('<>:"/\\|?*')

#: 单个路径段的最大长度。
MAX_SEGMENT_LENGTH = 255

#: Windows 在把名称交给底层 API 之前会丢弃的尾部字符。
TRAILING_CHARS = " ."


def has_illegal_chars(name):
    """``name`` 中是否含 Win32 非法字符。"""
    return any(ch in ILLEGAL_CHARS for ch in name)


def is_reserved(name):
    """``name`` 是否是 Windows 保留设备名。"""
    return name.strip().upper() in RESERVED_BASE_NAMES


def is_valid(name):
    """``name`` 能否在 Windows 目标文件系统上直接使用，无需净化。"""
    if not name or not name.strip():
        return False
    if len(name) > MAX_SEGMENT_LENGTH:
        return False
    if has_illegal_chars(name):
        return False
    return not is_reserved(name)
