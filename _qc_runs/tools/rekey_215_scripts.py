"""把 216 的归档/截图/上传脚本改键为 215（wfmt-215 v2.1.0）版本。"""

from __future__ import annotations

import shutil
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
SRC_TOOLS = WS / "_qc_runs" / "tools"
DST = WS / "deliverables" / "2026-10-10_wfmt215-返修"

FILES = {
    "assemble_216_jobs_archive.py": "assemble_215_jobs_archive.py",
    "verify_216_v12_archive.py": "verify_215_v21_archive.py",
    "make_216_v12_screenshots.py": "make_215_v21_screenshots.py",
    "submit_216_replace118_A.ps1": "submit_215_replace143_A.ps1",
}

REPLACEMENTS = [
    # 路径（先长后短，避免部分替换）
    (r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修",
     r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-10_wfmt215-返修"),
    ("2026-10-11_wchunk216-返修", "2026-10-10_wfmt215-返修"),
    ("deliverables/2026-10-11_wchunk216-返修", "deliverables/2026-10-10_wfmt215-返修"),
    # 标识符
    ("wfflab__wchunk-216", "wfflab__wfmt-215"),
    ("wfflab/wchunk-216", "wfflab/wfmt-215"),
    ("wchunk-216", "wfmt-215"),
    ("wchunk_semantics", "wfmt_semantics"),
    ("WChunkError", "WFormatError"),
    ('"wchunk"', '"wfmt"'),
    ("/wchunk", "/wfmt"),
    ("wchunk", "wfmt"),
    # 版本与产物
    ("1.2.0", "2.1.0"),
    ("v1.2.0", "v2.1.0"),
    ("v1.1.0", "v2.0.0"),
    # 飞书记录
    ("reczz28KQU8reW2k", "reczz28KwEOO3xHy"),
    ("wfflab__wchunk-216-v1.2.0-delivery.zip", "wfflab__wfmt-215-v2.1.0-delivery.zip"),
]


def main() -> None:
    for src_name, dst_name in FILES.items():
        src = SRC_TOOLS / src_name
        dst = DST / dst_name
        text = src.read_text(encoding="utf-8")
        for old, new in REPLACEMENTS:
            text = text.replace(old, new)
        dst.write_text(text, encoding="utf-8", newline="\n")
        print(f"{src_name:32} -> {dst_name}")


if __name__ == "__main__":
    main()
