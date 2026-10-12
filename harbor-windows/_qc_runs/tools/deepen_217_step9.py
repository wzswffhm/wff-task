"""217 加深（第九步）：修复可见冒烟测试的脚本编码。

Windows PowerShell 5.1 读取无 BOM 的 UTF-8 脚本时按 ANSI（当前代码页）解析。
注释里的中文乱码无害（现有 prepare.ps1 / run_tests.ps1 就是如此），但中文字符串
字面量被误读后会产生非法 token（实测报 'Array index expression is missing'）。

处置：把 tests/test_wreparse_basic.ps1 重写为 UTF-8 with BOM，使 5.1 正确按 UTF-8 解析。
"""
from __future__ import annotations

import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
SMOKE = TASK / "environment/workspace/tests/test_wreparse_basic.ps1"

text = SMOKE.read_text(encoding="utf-8")
# 写入 UTF-8 BOM + 内容
SMOKE.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

raw = SMOKE.read_bytes()
print(f"ok {SMOKE.name}: 写入 {len(raw)} 字节，BOM={'有' if raw[:3] == b'\\xef\\xbb\\xbf' else '无'}")
print(f"   首 3 字节 = {raw[:3].hex(' ')}")

print("\nRESULT: 第九步完成")
