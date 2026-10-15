"""Thin ctypes bindings for the token calls :mod:`wtoken` needs.

Only what the current implementation actually calls is bound here; the library
is loaded lazily so that importing the package stays cheap.
"""

import os

_IS_WINDOWS = os.name == "nt"


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def _advapi32():
    import ctypes

    return ctypes.WinDLL("advapi32", use_last_error=True)


def _kernel32():
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)


def last_error():
    import ctypes

    return ctypes.get_last_error()


def current_process():
    """Return a pseudo handle for the current process."""
    import ctypes
    from ctypes import wintypes

    func = _kernel32().GetCurrentProcess
    func.restype = wintypes.HANDLE
    return func()


def open_process_token(access):
    """Open the current process token with ``access``. Returns the handle."""
    import ctypes
    from ctypes import wintypes

    if not _IS_WINDOWS:
        raise OSError("process tokens exist only on Windows")
    handle = wintypes.HANDLE()
    func = _advapi32().OpenProcessToken
    func.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    func.restype = wintypes.BOOL
    if not func(current_process(), access, ctypes.byref(handle)):
        raise OSError(last_error(), "OpenProcessToken failed")
    return handle


def close_handle(handle):
    import ctypes
    from ctypes import wintypes

    func = _kernel32().CloseHandle
    func.argtypes = [wintypes.HANDLE]
    func.restype = wintypes.BOOL
    func(wintypes.HANDLE(int(handle)))
