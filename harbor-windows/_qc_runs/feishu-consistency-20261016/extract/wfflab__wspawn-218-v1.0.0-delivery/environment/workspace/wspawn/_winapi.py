"""Thin ctypes bindings for the Win32 calls that :mod:`wspawn` needs.

Only what the current implementation actually calls is bound here; the DLL is
loaded lazily so that importing the package stays cheap.
"""

import os

FILE_TYPE_UNKNOWN = 0x0000
FILE_TYPE_DISK = 0x0001
FILE_TYPE_CHAR = 0x0002
FILE_TYPE_PIPE = 0x0003
FILE_TYPE_REMOTE = 0x8000

_IS_WINDOWS = os.name == "nt"


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def _kernel32():
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)


def file_type(handle):
    """Return the ``GetFileType`` value for an object handle."""
    if not _IS_WINDOWS:
        raise OSError("GetFileType is only available on Windows")
    import ctypes
    from ctypes import wintypes

    func = _kernel32().GetFileType
    func.argtypes = [wintypes.HANDLE]
    func.restype = wintypes.DWORD
    return int(func(wintypes.HANDLE(int(handle))))
