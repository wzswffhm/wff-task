"""Stage 1: split the delivered tree into an agent-visible package and a
verifier-side (injected) tree.

Input : <root>/build/outside_harbor-assets/wfflab__wchunk-216
Output: <root>/build/outside_harbor-verifier/wfflab__wchunk-216

Nothing is invented here: files are moved out of the agent-visible tree, never
rewritten, so the diff stays auditable.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")
BUILD = ROOT / "build"
TASK = BUILD / "outside_harbor-assets" / "wfflab__wchunk-216"
VER = BUILD / "outside_harbor-verifier" / "wfflab__wchunk-216"
TASK_ID = "wfflab__wchunk-216"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        raise SystemExit(f"missing source: {src}")
    shutil.move(str(src), str(dst))
    print(f"move  {src.relative_to(BUILD)}  ->  {dst.relative_to(BUILD)}")


def main() -> None:
    if VER.exists():
        shutil.rmtree(VER)
    VER.mkdir(parents=True, exist_ok=True)

    # 1. hidden behavioural suite -> verifier side
    move(TASK / "tests" / "hidden" / "test_wchunk_semantics.py", VER / "tests" / "test_wchunk_semantics.py")
    hidden_dir = TASK / "tests" / "hidden"
    if hidden_dir.exists():
        shutil.rmtree(hidden_dir)
        print("rmdir tests/hidden")

    # 2. golden reference implementation -> verifier side (oracle)
    move(TASK / "solution" / "reference", VER / "oracle" / "reference")
    # The original solution README explains the fix; it must not stay in the
    # agent-visible tree. Keep it on the verifier side as an audit record.
    original_readme = TASK / "solution" / "README.md"
    if original_readme.exists():
        move(original_readme, VER / "oracle" / "README-original.md")
    oracle_patch = TASK / "solution" / "oracle.patch"
    if oracle_patch.exists():
        move(oracle_patch, VER / "oracle" / "oracle.patch")
    move(TASK / "solution" / "solve.ps1", VER / "oracle" / "solve.ps1")
    move(TASK / "solution" / "solve.bat", VER / "oracle" / "solve.bat")

    # 3. previous verifier run artefacts -> verifier side evidence
    if (TASK / "verifier").exists():
        move(TASK / "verifier", VER / "evidence" / "verifier-run")

    # 4. record hashes of everything that left the agent-visible tree
    manifest = []
    for path in sorted(VER.rglob("*")):
        if path.is_file():
            manifest.append({
                "path": str(path.relative_to(VER)).replace("\\", "/"),
                "sha256": sha256(path),
                "size": path.stat().st_size,
            })
    (VER / "SEALED_MANIFEST.json").write_text(
        json.dumps({
            "task_id": TASK_ID,
            "note": "Verifier-side material. Never injected into the agent environment.",
            "files": manifest,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"sealed files: {len(manifest)}")


if __name__ == "__main__":
    main()
