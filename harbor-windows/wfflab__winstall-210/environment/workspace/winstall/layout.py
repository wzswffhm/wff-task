"""安装根的布局规则。

两个作用域（scope）互相独立：

* ``machine`` —— 整机安装，落在 ``%ProgramData%\\WInstall``
* ``user``    —— 单用户安装，落在 ``%LOCALAPPDATA%\\WInstall``

目录形状::

    <root>/
        installed.json            # 清单
        products/
            <product>/
                payload/          # 已安装的文件（升级时原地覆盖）
"""

import os

MANIFEST_NAME = "installed.json"
PRODUCTS_DIR = "products"

_MACHINE_FALLBACK = r"C:\ProgramData"
_USER_FALLBACK = r"C:\Users\Default\AppData\Local"


def install_root(scope="machine", base=None):
    """返回某个作用域的安装根。

    ``base`` 用于测试或便携部署：显式给出时直接作为根使用。
    """
    if base:
        return os.path.abspath(str(base))
    if scope == "machine":
        env = os.environ.get("ProgramData") or _MACHINE_FALLBACK
    elif scope == "user":
        env = os.environ.get("LOCALAPPDATA")
        if not env:
            profile = os.environ.get("USERPROFILE") or ""
            env = os.path.join(profile, "AppData", "Local") if profile else _USER_FALLBACK
    else:
        raise ValueError("unknown scope: %r" % (scope,))
    return os.path.join(env, "WInstall")


def products_root(root):
    return os.path.join(root, PRODUCTS_DIR)


def product_dir(root, product):
    return os.path.join(products_root(root), product)


def payload_dir(root, product):
    """产品载荷的落盘位置。升级时在原地覆盖，不保留旧版本目录。"""
    return os.path.join(product_dir(root, product), "payload")


def normalize_key(path):
    """把路径归一成比较用的键。

    Windows 的路径比较不区分大小写，分隔符也允许混用。
    """
    return os.path.normcase(os.path.normpath(str(path)))


def relative_key(relpath):
    """把载荷内的相对路径归一成 POSIX 风格，作为清单里的稳定键。"""
    return str(relpath).replace("\\", "/").strip("/")
