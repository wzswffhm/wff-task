"""修正 215 脚本里从 216 继承来的残留（check 数、上游 sha256、自述文件名）。"""

from __future__ import annotations

from pathlib import Path

D = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-10_wfmt215-返修")

FIXES = {
    "verify_215_v21_archive.py": [
        ("verify_216_v12_archive.py", "verify_215_v21_archive.py"),
        ('len(vr.get("items", [])) == 18', 'len(vr.get("items", [])) == 15'),
        ("items 应为 18 项", "items 应为 15 项"),
    ],
    "assemble_215_jobs_archive.py": [
        ("assemble_216_jobs_archive.py", "assemble_215_jobs_archive.py"),
        ("prepare_216_delivery.py", "_stage4_metadata.py"),
        ('ORIGINAL_DOWNLOAD_SHA256 = "d215e87f8039d0e7d4387400177f22f198c0b28bbfa65f56e23f45a9278e73f1"',
         'ORIGINAL_DOWNLOAD_SHA256 = "ad1478b3d03f24b6bb52aa62679b16494020974d185ed5772d9b6c922a24c492"'),
    ],
    "make_215_v21_screenshots.py": [
        ("make_216_v12_screenshots.py", "make_215_v21_screenshots.py"),
    ],
}


def main() -> None:
    for name, pairs in FIXES.items():
        path = D / name
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            count = text.count(old)
            text = text.replace(old, new)
            print(f"{name:34} {old[:48]!r:52} x{count}")
        path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
