"""安装清单（``installed.json``）的读写。

清单是安装状态的唯一权威记录，形状如下::

    {
      "schema": 1,
      "products": {
        "<product>": {
          "version": "1.2.3",
          "files": ["bin/app.exe", "etc/app.ini"],
          "pending_replace": ["bin/locked.dll"]
        }
      }
    }

``pending_replace`` 记录那些**因为被其它进程占用而暂时无法替换**的文件。
它们仍然以旧内容留在原处，等待下一次执行时完成替换。
"""

import json
import os

from . import layout

SCHEMA = 1


def manifest_path(root):
    return os.path.join(root, layout.MANIFEST_NAME)


def empty():
    return {"schema": SCHEMA, "products": {}}


def read_manifest(root):
    """读取清单；不存在或损坏时返回空清单。"""
    path = manifest_path(root)
    if not os.path.isfile(path):
        return empty()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return empty()
    if not isinstance(data, dict):
        return empty()
    data.setdefault("schema", SCHEMA)
    products = data.get("products")
    if not isinstance(products, dict):
        data["products"] = {}
    return data


def write_manifest(root, data):
    """原子写入清单。"""
    os.makedirs(root, exist_ok=True)
    path = manifest_path(root)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def get_product(data, product):
    entry = (data.get("products") or {}).get(product)
    if not isinstance(entry, dict):
        return None
    return entry


def set_product(data, product, version, files, pending_replace=None):
    data.setdefault("products", {})[product] = {
        "version": str(version),
        "files": [layout.relative_key(f) for f in files],
        "pending_replace": [layout.relative_key(f) for f in (pending_replace or [])],
    }


def drop_product(data, product):
    (data.get("products") or {}).pop(product, None)
