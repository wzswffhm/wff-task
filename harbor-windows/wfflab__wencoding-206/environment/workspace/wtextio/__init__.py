"""wtextio —— 面向跨平台交换的文本读写。

工具链常常在 Windows 上生成文本、在别处消费它。只要编码选错，中文、重音字母
就会变成问号或者直接抛异常。本库把编码选择集中到一处，默认使用 UTF-8。
"""

from .codec import ALIASES, BOM_ENCODING, DEFAULT_ENCODING, encoding_for, known_encodings, system_encoding
from .reader import detect_bom, read_lines, read_text
from .writer import append_text, write_lines, write_text

__version__ = "1.3.0"

__all__ = [
    "ALIASES",
    "BOM_ENCODING",
    "DEFAULT_ENCODING",
    "append_text",
    "detect_bom",
    "encoding_for",
    "known_encodings",
    "read_lines",
    "read_text",
    "system_encoding",
    "write_lines",
    "write_text",
]
