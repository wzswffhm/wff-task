"""有效权限判定。

Windows 的访问控制模型里，**显式拒绝优先于允许**：只要有一条拒绝项命中，
该权限就是不予授予，哪怕同时存在允许项。
"""

from .icacls import list_aces

#: 表示「可写」的权限字母。
WRITE_RIGHTS = frozenset({"W", "M", "F"})

#: 表示「可读」的权限字母（写与完全控制都隐含读）。
READ_RIGHTS = frozenset({"R", "RX", "F", "M", "W"})


def effective_rights(path, principal):
    """返回 ``principal`` 在 ``path`` 上被允许与被拒绝的权限集合。"""
    allow = set()
    deny = set()
    for ace in list_aces(path):
        if ace.principal.upper() != principal.upper():
            continue
        if ace.deny:
            deny |= ace.rights
        else:
            allow |= ace.rights
    return allow, deny


def can_write(path, principal):
    """``principal`` 能否在 ``path`` 上写入。"""
    allow, _deny = effective_rights(path, principal)
    return bool(allow & WRITE_RIGHTS)


def can_read(path, principal):
    """``principal`` 能否在 ``path`` 上读取。"""
    allow, deny = effective_rights(path, principal)
    if deny & READ_RIGHTS:
        return False
    return bool(allow & READ_RIGHTS)
