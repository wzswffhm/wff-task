"""wpublish —— 把构建产物发布到 Windows 共享目录。

发布时不仅要复制文件，还要把访问权限一并摆正：共享目录里的内容应当
对访问者只读，并且这个限制必须覆盖整个子树，而不只是根目录。
"""

from .errors import ICaclsError, WPublishError
from .icacls import (
    Ace,
    deny,
    disable_inheritance,
    grant,
    list_aces,
    list_explicit_aces,
    parse_aces,
    run,
)
from .publish import READONLY_SPEC, all_principals, audit, explicit_grants, publish
from .rights import READ_RIGHTS, WRITE_RIGHTS, can_read, can_write, effective_rights

__version__ = "1.9.0"

__all__ = [
    "Ace",
    "ICaclsError",
    "READONLY_SPEC",
    "WPublishError",
    "WRITE_RIGHTS",
    "all_principals",
    "audit",
    "can_read",
    "can_write",
    "deny",
    "disable_inheritance",
    "effective_rights",
    "explicit_grants",
    "grant",
    "list_aces",
    "list_explicit_aces",
    "parse_aces",
    "publish",
    "run",
]
