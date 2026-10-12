"""把 215 返修脚本机械改键为 216 版（只做标识符/路径替换，内容语义随后逐段人工核对）。"""

from __future__ import annotations

from pathlib import Path

DST = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")

REPLACEMENTS = [
    ("C:\\Users\\Administrator\\Desktop\\wff-task\\deliverables\\2026-10-10_wfmt215-返修",
     "C:\\Users\\Administrator\\Desktop\\wff-task\\deliverables\\2026-10-11_wchunk216-返修"),
    ("wfflab__wfmt-215", "wfflab__wchunk-216"),
    ("WFMT_VERIFIER_ROOT", "WCHUNK_VERIFIER_ROOT"),
    ("WFormatError", "WChunkError"),
    ("wfmt", "wchunk"),
    ("2.1.0", "1.2.0"),
    ("wfflab/wfmt-215", "wfflab/wchunk-216"),
]


def main() -> None:
    for path in sorted(DST.glob("_*.py")):
        text = path.read_text(encoding="utf-8")
        original = text
        hits = {}
        for old, new in REPLACEMENTS:
            count = text.count(old)
            if count:
                hits[old] = count
                text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8", newline="\n")
        print(f"{path.name:28} {'; '.join(f'{k!r} x{v}' for k, v in hits.items()) or 'no change'}")


if __name__ == "__main__":
    main()
