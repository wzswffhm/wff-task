"""版本号解析与比较。

Windows 产品的版本号习惯是 ``major.minor.build.revision`` 四段十进制，
末尾段可以省略（省略视作 0），并且允许 ``1.2.3.4-beta.1`` 这样的预发布标签。
"""

_STRIP = "vV"


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


def _segments(numbers):
    """把 ``1.10.0`` 这样的数字部分转成整数元组，不足四段补 0。"""
    out = []
    for item in numbers.split("."):
        if not item.isdigit():
            raise ValueError("invalid version segment: %r" % (item,))
        out.append(int(item))
    while len(out) < 4:
        out.append(0)
    return tuple(out)


def parse_version(text):
    """把版本号拆成段落列表。

    段之间用 ``.`` 分隔，统一转成十进制整数并补齐到四段。
    """
    numbers, _prerelease = split_version(text)
    return list(_segments(numbers))


def compare_versions(left, right):
    """比较两个版本号。

    返回 ``-1`` / ``0`` / ``1``。数字段按**数值**比较（``1.10.0`` 高于 ``1.9.0``），
    预发布版本低于同号的正式版。
    """
    left_numbers, left_pre = split_version(left)
    right_numbers, right_pre = split_version(right)
    left_segments = _segments(left_numbers)
    right_segments = _segments(right_numbers)
    if left_segments != right_segments:
        return 1 if left_segments > right_segments else -1
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
