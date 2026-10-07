"""wscan —— Windows 磁盘扫描与硬链接去重工具。

对外承诺：
- ``scan_tree``：目录树的文件清单、总字节与硬链接簇（按文件身份分组），
  遍历不进入任何重解析点目录（junction / 目录符号链接）；
- ``dedupe``：把内容重复的文件安全替换为指向规范的硬链接。
"""

from .dupes import dedupe
from .errors import WScanError
from .scan import ScanResult, scan_tree

__all__ = ["WScanError", "ScanResult", "scan_tree", "dedupe"]
