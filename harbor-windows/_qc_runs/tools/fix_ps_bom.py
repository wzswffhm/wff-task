"""给含非 ASCII 字符、且缺少 UTF-8 BOM 的 PowerShell 脚本补上 BOM。

Windows PowerShell 5.1 读取无 BOM 的 UTF-8 脚本时按 ANSI 代码页解析；
ASCII 内容不受影响，但中文字符串字面量会被误读成非法 token。
注释里的乱码无害，字符串字面量里的乱码会直接导致语法错误。

用法：python fix_ps_bom.py <文件或目录> [...]
"""
from __future__ import annotations

import sys
from pathlib import Path

BOM = b"\xef\xbb\xbf"


def needs_fix(path: Path) -> tuple[bool, str]:
    raw = path.read_bytes()
    if raw.startswith(BOM):
        return False, "已有 BOM"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False, "不是 UTF-8"
    if text.isascii():
        return False, "纯 ASCII，无需 BOM"
    return True, "含非 ASCII 且无 BOM"


def main(targets: list[str]) -> int:
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.ps1")))
        elif p.suffix.lower() == ".ps1":
            files.append(p)
        else:
            print(f"跳过（非 .ps1）: {p}")
    changed = 0
    for f in files:
        fix, why = needs_fix(f)
        if fix:
            f.write_bytes(BOM + f.read_bytes())
            print(f"  fixed  {f.name}  ({why})")
            changed += 1
        else:
            print(f"  ok     {f.name}  ({why})")
    print(f"\n共检查 {len(files)} 个脚本，修复 {changed} 个")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
