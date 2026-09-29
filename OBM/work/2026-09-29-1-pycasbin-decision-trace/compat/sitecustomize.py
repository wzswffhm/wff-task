"""Windows compatibility shim for the OBM Seed orchestration scripts.

Loaded automatically (sitecustomize) when this directory is on PYTHONPATH.
Only active on win32; it changes nothing on Linux.

- ``os.getuid`` / ``os.getgid``: ``run_seed_agent.py`` builds a docker
  ``--user`` flag from them. On Windows there is no such API, so we run the
  command container as root (``0:0``) — the only identity guaranteed to write
  into a Docker Desktop bind mount of an NTFS directory.
- ``os.killpg`` / ``os.setsid``: used only by the monitor's timeout and
  interrupt paths. Stubbed so termination falls back to
  ``process.terminate()`` / ``process.kill()`` instead of raising
  ``AttributeError`` inside an ``except (OSError, ...)`` clause.
"""

import os
import signal
import sys

if sys.platform == "win32":
    if not hasattr(os, "getuid"):
        os.getuid = lambda: 0  # type: ignore[attr-defined]
    if not hasattr(os, "getgid"):
        os.getgid = lambda: 0  # type: ignore[attr-defined]
    if not hasattr(os, "killpg"):
        def _killpg(pgid, sig):  # type: ignore[no-untyped-def]
            return None
        os.killpg = _killpg  # type: ignore[attr-defined]
    if not hasattr(os, "setsid"):
        os.setsid = lambda: None  # type: ignore[attr-defined]
    # monitor_seed_experiment.py references signal.SIGKILL / SIGTERM when
    # terminating a timed-out child; SIGKILL does not exist on Windows.
    if not hasattr(signal, "SIGKILL"):
        signal.SIGKILL = signal.SIGTERM  # type: ignore[attr-defined]
