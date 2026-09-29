"""Run obm-task-production/scripts/task_registry.py on Windows.

The script imports `fcntl`, which does not exist on Windows. This wrapper
injects a no-op file-lock module so the same command line works unchanged.
It is only valid for a single-window run: cross-process mutual exclusion is
NOT provided by the stub. Do not rely on it when several windows reserve
task ids at the same time.
"""
from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path

SCRIPT = Path(
    r"C:\Users\Administrator\Desktop\OBM\skills\obm-task-production\scripts\task_registry.py"
)


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
    install_fcntl_stub()
    sys.argv = [str(SCRIPT), *sys.argv[1:]]
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
