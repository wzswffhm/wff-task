"""版本号解析与比较（等价实现：用定宽十进制串做比较键）。

与参考解的差别只在实现手法：这里不比较整数元组，而是把每一段格式化成
固定宽度的十进制串再拼接，用字符串比较得到同样的排序。
"""

_STRIP = "vV"
_WIDTH = 12


def normalize(text):
    """去掉可选的 ``v`` 前缀与首尾空白。"""
    value = str(text).strip()
    while value[:1] in _STRIP:
        value = value[1:]
    return value


def split_version(text):
    """把版本号拆成 ``(数字部分, 预发布标签)``。"""
    value = normalize(text)
    if "-" in value:
        numbers, prerelease = value.split("-", 1)
    else:
        numbers, prerelease = value, ""
    return numbers, prerelease.strip()


def parse_version(text):
    """把版本号拆成段落列表（十进制整数，至少四段）。"""
    numbers, _prerelease = split_version(text)
    out = []
    for item in numbers.split("."):
        if not item.isdigit():
            raise ValueError("invalid version segment: %r" % (item,))
        out.append(int(item))
    while len(out) < 4:
        out.append(0)
    return out


def _sort_key(text):
    """把数字部分变成定宽十进制串；按字串比较即等价于按数值比较。"""
    return "".join("%0*d" % (_WIDTH, value) for value in parse_version(text))


def compare_versions(left, right):
    """比较两个版本号，返回 ``-1`` / ``0`` / ``1``。"""
    left_key = _sort_key(left)
    right_key = _sort_key(right)
    if left_key != right_key:
        return 1 if left_key > right_key else -1
    _ln, left_pre = split_version(left)
    _rn, right_pre = split_version(right)
    if left_pre == right_pre:
        return 0
    if not left_pre:
        return 1
    if not right_pre:
        return -1
    return 1 if left_pre > right_pre else -1


def is_upgrade(current, candidate):
    """``candidate`` 是否严格高于 ``current``。"""
    return compare_versions(candidate, current) > 0
