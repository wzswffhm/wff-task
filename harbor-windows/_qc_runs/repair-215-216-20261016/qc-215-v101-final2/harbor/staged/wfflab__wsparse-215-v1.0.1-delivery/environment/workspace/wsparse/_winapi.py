"""Thin ctypes bindings for the Win32 calls that :mod:`wsparse` needs.

Only the calls the current implementation actually uses are bound here. The
module is written so that importing it on a non-Windows platform stays cheap:
the DLL is loaded lazily, on first use.
"""

import os

# FILE_ATTRIBUTE_SPARSE_FILE
SPARSE_ATTRIBUTE = 0x00000200

_IS_WINDOWS = os.name == "nt"


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def _kernel32():
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)
