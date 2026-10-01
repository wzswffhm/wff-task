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


def parse_version(text):
    """把版本号拆成段列表。

    段之间用 ``.`` 分隔，不足四段的按原样返回（由调用方决定如何补齐）。
    """
    numbers, _prerelease = split_version(text)
    return numbers.split(".")


def compare_versions(left, right):
    """比较两个版本号。

    返回 ``-1`` / ``0`` / ``1``。预发布版本低于同号的正式版。
    """
    left_numbers, left_pre = split_version(left)
    right_numbers, right_pre = split_version(right)
    if left_numbers == right_numbers:
        if left_pre == right_pre:
            return 0
        if not left_pre:
            return 1
        if not right_pre:
            return -1
        return 1 if left_pre > right_pre else -1
    return 1 if left_numbers > right_numbers else -1


def is_upgrade(current, candidate):
    """``candidate`` 是否严格高于 ``current``。"""
    return compare_versions(candidate, current) > 0
