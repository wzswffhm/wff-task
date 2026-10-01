"""把文本写入文件。"""

from .codec import encoding_for


def write_text(path, text, encoding="default", newline="\r\n"):
    """把 ``text`` 写入 ``path``，返回写入的字符数。"""
    with open(path, "w", encoding=encoding_for(encoding), newline=newline) as fh:
        fh.write(text)
    return len(text)


def append_text(path, text, encoding="default"):
    """在 ``path`` 末尾追加 ``text``，返回追加的字符数。"""
    with open(path, "a", encoding=encoding_for(encoding), newline="\r\n") as fh:
        fh.write(text)
    return len(text)


def write_lines(path, lines, encoding="default"):
    """把若干行写成文本文件，返回写入的行数。"""
    return write_text(path, "\r\n".join(lines) + "\r\n", encoding=encoding) if lines else write_text(
        path, "", encoding=encoding
    )
