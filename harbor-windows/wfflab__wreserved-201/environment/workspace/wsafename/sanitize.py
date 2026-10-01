"""把用户提供的名称转换成可以安全落盘的名称。"""

from .errors import InvalidNameError
from .rules import ILLEGAL_CHARS, MAX_SEGMENT_LENGTH

#: 替换非法字符时使用的字符。
REPLACEMENT = "_"


def sanitize(name, replacement=REPLACEMENT):
    """把 ``name`` 转换成可以在 Windows 上落盘的单个路径段。

    处理顺序：

    1. 去掉首尾空白
    2. 把非法字符替换为 ``replacement``
    3. 截断到 :data:`wsafename.rules.MAX_SEGMENT_LENGTH`

    返回净化后的名称。``name`` 不是字符串时抛 ``TypeError``；
    净化结果不可用时抛 :class:`InvalidNameError`。
    """
    if not isinstance(name, str):
        raise TypeError("name must be str, got %s" % type(name).__name__)

    cleaned = name.strip()

    out = [replacement if ch in ILLEGAL_CHARS else ch for ch in cleaned]
    cleaned = "".join(out)

    if len(cleaned) > MAX_SEGMENT_LENGTH:
        cleaned = cleaned[:MAX_SEGMENT_LENGTH]

    if not cleaned:
        raise InvalidNameError("name is empty after sanitizing: %r" % (name,))

    return cleaned
