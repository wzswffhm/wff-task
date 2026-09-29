"""Generic Windows launcher for OBM skill scripts.

The OBM skill scripts import `fcntl`, which does not exist on Windows. This
wrapper injects a no-op file-lock module, puts the target script's directory on
sys.path (so sibling imports such as `import task_registry` resolve), and then
runs the script with the remaining CLI arguments.

Usage:
    python work/win_skill_run.py <path-to-skill-script.py> [script args...]

The working directory is left untouched, so `--root .` still refers to the
project root the command was started from.

NOTE: the fcntl stub provides NO cross-process mutual exclusion. It is safe for
single-window runs only. Do not rely on it when several windows reserve task
ids concurrently.
"""
from __future__ import annotations

import os
import runpy
import sys
import types
from pathlib import Path


def install_fcntl_stub() -> None:
    if "fcntl" in sys.modules:
        return
    module = types.ModuleType("fcntl")
    module.LOCK_EX = 2
    module.LOCK_SH = 1
    module.LOCK_UN = 8
    module.LOCK_NB = 4
    module.F_TLOCK = 2
    module.F_ULOCK = 0

    def _noop(*args, **kwargs):
        return None

    module.flock = _noop
    module.lockf = _noop
    module.fcntl = _noop
    sys.modules["fcntl"] = module


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    script = Path(sys.argv[1]).resolve()
    if not script.is_file():
        print("script not found: {}".format(script))
        return 2
    install_fcntl_stub()
    script_dir = str(script.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    sys.argv = [str(script), *sys.argv[2:]]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
