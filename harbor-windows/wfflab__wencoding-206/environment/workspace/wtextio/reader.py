"""从文件读回文本。"""

from .codec import encoding_for


def read_text(path, encoding="default"):
    """读回整个文件。"""
    with open(path, "r", encoding=encoding_for(encoding), newline="") as fh:
        return fh.read()


def read_lines(path, encoding="default"):
    """读回文件并按行切分（不含行尾）。"""
    return read_text(path, encoding=encoding).splitlines()


def detect_bom(path):
    """返回文件开头的字节序标记名称；没有时返回 ``None``。"""
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8"
    if head.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if head.startswith(b"\xfe\xff"):
        return "utf-16-be"
    return None
