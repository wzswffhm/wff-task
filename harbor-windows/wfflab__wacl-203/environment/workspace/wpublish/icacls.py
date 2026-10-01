"""icacls 的薄封装。

NTFS 的访问控制列表（ACL）由若干访问控制项（ACE）组成，每项描述
「某个主体在该对象上被允许或拒绝哪些权限」。系统管理员在命令行上通过
``icacls`` 读写它们；这里把它包成可测试的接口。
"""

import re
import subprocess

from .errors import ICaclsError

#: icacls 可执行文件名。
ICACLS = "icacls"

#: 只在目录上有意义的继承标志，不参与权限集合。
_INHERITANCE_FLAGS = frozenset({"OI", "CI", "IO", "NP"})

_ACE_RE = re.compile(r"^\s*(.+?):((?:\([^)]*\))+)\s*$")
_TOKEN_RE = re.compile(r"\(([^)]*)\)")


class Ace(object):
    """一条访问控制项。"""

    __slots__ = ("principal", "rights", "deny", "inherited")

    def __init__(self, principal, rights, deny=False, inherited=False):
        self.principal = principal
        self.rights = frozenset(rights)
        self.deny = deny
        self.inherited = inherited

    def __repr__(self):
        return "Ace(%r, %r, deny=%r, inherited=%r)" % (
            self.principal,
            sorted(self.rights),
            self.deny,
            self.inherited,
        )


def run(path, *args):
    """对 ``path`` 执行 icacls，返回标准输出。"""
    cmd = [ICACLS, path] + [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ICaclsError(
            "icacls %s failed with %d: %s"
            % (path, proc.returncode, (proc.stdout or "").strip())
        )
    return proc.stdout


def parse_aces(output):
    """把 icacls 的输出解析成 :class:`Ace` 列表。"""
    aces = []
    for line in output.splitlines():
        m = _ACE_RE.match(line)
        if not m:
            continue
        principal = m.group(1).strip()
        tokens = [t.strip().upper() for t in _TOKEN_RE.findall(m.group(2))]
        deny = "DENY" in tokens
        inherited = "I" in tokens
        rights = {
            t for t in tokens if t and t not in _INHERITANCE_FLAGS and t not in ("DENY", "I")
        }
        if not rights:
            continue
        aces.append(Ace(principal, rights, deny=deny, inherited=inherited))
    return aces


def list_aces(path):
    """返回 ``path`` 上的全部访问控制项。"""
    return parse_aces(run(path))


def list_explicit_aces(path):
    """返回 ``path`` 上**显式设置**的访问控制项。

    从父目录继承来的项不算显式设置。
    """
    return list_aces(path)


def deny(path, principal, spec, recursive=False):
    """在 ``path`` 上为主体添加一条拒绝项。

    ``spec`` 是 icacls 的权限说明，例如 ``"(OI)(CI)(RX)"``。
    """
    args = ["/deny", "%s:%s" % (principal, spec)]
    if recursive:
        args.append("/T")
    return run(path, *args)


def grant(path, principal, spec, recursive=False):
    """在 ``path`` 上为主体添加一条允许项。"""
    args = ["/grant", "%s:%s" % (principal, spec)]
    if recursive:
        args.append("/T")
    return run(path, *args)


def disable_inheritance(path):
    """移除 ``path`` 上从父目录继承来的项。"""
    return run(path, "/inheritance:r")
