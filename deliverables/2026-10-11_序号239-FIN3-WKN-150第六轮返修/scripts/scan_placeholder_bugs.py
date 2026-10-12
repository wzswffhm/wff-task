# -*- coding: utf-8 -*-
"""扫描复算脚本中「普通字符串却含 {占位符}」的可疑行，定位字符串插值缺陷。"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

TARGETS = [
    pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-150"
                 r"\solution\golden_output\FIN3-WKN-150_reproduce.py"),
    pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-150"
                 r"\tests\__golden_output\FIN3-WKN-150_reproduce.py"),
]

# 匹配「非 f 前缀」的字符串起始：' 或 " 或 ''' / """，前面允许 ( , = 空格
PLAIN = re.compile(r"(?<![fF])(?P<q>'''|\"\"\"|'|\")")


def suspicious(line: str) -> bool:
    """该行是否以普通字符串开头且包含花括号占位符。"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    for m in PLAIN.finditer(line):
        # 跳过 f''' / f" 等（由负向后视处理），也跳过已是 f 前缀
        start = m.end()
        rest = line[start:]
        if "{" in rest and ("}" in rest):
            # 排除字典/集合字面量：花括号内不含 : 格式说明且形如 {'a': 1}
            for frag in re.findall(r"\{[^{}]*\}", rest):
                inner = frag[1:-1]
                # 形如 {name}、{name:...}、{obj["k"]}、{expr * 100:.1f} 视为占位符
                # 形如 {'a': 1} / {"a": 1} / {1, 2} 视为字面量
                if re.search(r"['\"][^'\"]*['\"]\s*:", inner) or re.fullmatch(
                        r"[\d,\s]+", inner):
                    continue
                return True
    return False


def main() -> int:
    for path in TARGETS:
        if not path.is_file():
            print(f"[缺失] {path}")
            continue
        print(f"=== {path} ===")
        hits = 0
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if suspicious(line):
                hits += 1
                print(f"  {n:4d}: {line[:150]}")
        print(f"  可疑行合计: {hits}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
