"""ctypes bindings for the token calls the wtoken contract needs.

Everything the module does to the process token passes through this file: the
privilege array is read with ``GetTokenInformation(TokenPrivileges)``, names and
identifiers are translated with ``LookupPrivilegeName`` /
``LookupPrivilegeValue``, the enabled bit is written with
``AdjustTokenPrivileges``, and elevation and the mandatory label come from
``TokenElevation`` / ``TokenElevationType`` / ``TokenIntegrityLevel``.
"""

import ctypes
import os
from ctypes import wintypes

# ---- token access rights ----------------------------------------------------
TOKEN_QUERY = 0x0008
TOKEN_ADJUST_PRIVILEGES = 0x0020

# ---- privilege attributes ---------------------------------------------------
SE_PRIVILEGE_ENABLED_BY_DEFAULT = 0x00000001
SE_PRIVILEGE_ENABLED = 0x00000002
SE_PRIVILEGE_REMOVED = 0x00000004
SE_PRIVILEGE_USED_FOR_ACCESS = 0x80000000

# ---- TOKEN_INFORMATION_CLASS values ----------------------------------------
TokenUser = 1
TokenGroups = 2
TokenPrivileges = 3
TokenElevationType = 18
TokenElevation = 20
TokenIntegrityLevel = 25

# ---- integrity RIDs ---------------------------------------------------------
INTEGRITY_UNTRUSTED = 0x0000
INTEGRITY_LOW = 0x1000
INTEGRITY_MEDIUM = 0x2000
INTEGRITY_MEDIUM_PLUS = 0x2100
INTEGRITY_HIGH = 0x3000
INTEGRITY_SYSTEM = 0x4000
INTEGRITY_PROTECTED = 0x5000

INTEGRITY_NAMES = {
    INTEGRITY_UNTRUSTED: "Untrusted",
    INTEGRITY_LOW: "Low",
    INTEGRITY_MEDIUM: "Medium",
    INTEGRITY_MEDIUM_PLUS: "Medium Plus",
    INTEGRITY_HIGH: "High",
    INTEGRITY_SYSTEM: "System",
    INTEGRITY_PROTECTED: "Protected Process",
}

ELEVATION_TYPE_NAMES = {
    1: "default",
    2: "full",
    3: "limited",
}

ERROR_NOT_ALL_ASSIGNED = 1300
ERROR_INVALID_PARAMETER = 87
ERROR_INVALID_HANDLE = 6
ERROR_NOT_SUPPORTED = 50
UNSUPPORTED_ERRORS = (ERROR_INVALID_PARAMETER, ERROR_INVALID_HANDLE, ERROR_NOT_SUPPORTED)

_IS_WINDOWS = os.name == "nt"

_advapi32 = None
_kernel32 = None


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", ctypes.c_long)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD),
                ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def kind_for_error(error):
    """Map a Win32 error code onto the :class:`WTokenError` taxonomy."""
    if error in UNSUPPORTED_ERRORS:
        return "unsupported"
    return "os"


def last_error():
    return ctypes.get_last_error()


def _declare_advapi(dll):
    dll.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.HANDLE)]
    dll.OpenProcessToken.restype = wintypes.BOOL
    dll.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    dll.GetTokenInformation.restype = wintypes.BOOL
    dll.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, wintypes.LPVOID,
                                          wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
    dll.AdjustTokenPrivileges.restype = wintypes.BOOL
    dll.LookupPrivilegeNameW.restype = wintypes.BOOL
    dll.LookupPrivilegeValueW.restype = wintypes.BOOL


def _declare_kernel(dll):
    dll.GetCurrentProcess.restype = wintypes.HANDLE
    dll.CloseHandle.argtypes = [wintypes.HANDLE]
    dll.CloseHandle.restype = wintypes.BOOL


def advapi32():
    global _advapi32
    if _advapi32 is None:
        if not _IS_WINDOWS:
            raise OSError("process tokens exist only on Windows")
        dll = ctypes.WinDLL("advapi32", use_last_error=True)
        _declare_advapi(dll)
        _advapi32 = dll
    return _advapi32


def kernel32():
    global _kernel32
    if _kernel32 is None:
        if not _IS_WINDOWS:
            raise OSError("process handles exist only on Windows")
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        _declare_kernel(dll)
        _kernel32 = dll
    return _kernel32


# ---- the token --------------------------------------------------------------

def open_process_token(access):
    """Open the current process token with ``access``. Returns the handle value."""
    handle = wintypes.HANDLE()
    if not advapi32().OpenProcessToken(kernel32().GetCurrentProcess(), access,
                                       ctypes.byref(handle)):
        raise OSError(last_error(), "OpenProcessToken failed")
    return handle.value


def close_handle(handle):
    if handle in (None, 0):
        return
    kernel32().CloseHandle(wintypes.HANDLE(int(handle)))


def get_token_information(handle, info_class, size_hint=0):
    """Read a variable-length token record and return its raw bytes."""
    needed = wintypes.DWORD(0)
    advapi32().GetTokenInformation(wintypes.HANDLE(int(handle)), info_class, None, 0,
                                   ctypes.byref(needed))
    size = max(int(needed.value), int(size_hint))
    if size <= 0:
        raise OSError(last_error(), "GetTokenInformation reported an empty record")
    buffer = ctypes.create_string_buffer(size)
    if not advapi32().GetTokenInformation(wintypes.HANDLE(int(handle)), info_class,
                                          buffer, size, ctypes.byref(needed)):
        raise OSError(last_error(), "GetTokenInformation failed")
    return buffer, int(needed.value)


def get_token_dword(handle, info_class):
    """Read a scalar token record."""
    value = wintypes.DWORD(0)
    needed = wintypes.DWORD(0)
    if not advapi32().GetTokenInformation(wintypes.HANDLE(int(handle)), info_class,
                                          ctypes.byref(value), ctypes.sizeof(value),
                                          ctypes.byref(needed)):
        raise OSError(last_error(), "GetTokenInformation failed")
    return int(value.value)


def read_privileges(handle):
    """Return ``[(name, luid_int, attributes), ...]`` from the token."""
    buffer, _ = get_token_information(handle, TokenPrivileges, ctypes.sizeof(TOKEN_PRIVILEGES))
    count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
    base = ctypes.addressof(buffer) + ctypes.sizeof(wintypes.DWORD)
    array = ctypes.cast(base, ctypes.POINTER(LUID_AND_ATTRIBUTES * count)).contents
    out = []
    for index in range(count):
        entry = array[index]
        out.append((lookup_privilege_name(entry.Luid), luid_to_int(entry.Luid),
                    int(entry.Attributes)))
    return out


def luid_to_int(luid):
    """Pack a LUID into a single integer."""
    return (int(luid.HighPart) << 32) | int(luid.LowPart)


def int_to_luid(value):
    """Unpack an integer into a LUID."""
    number = int(value)
    luid = LUID()
    luid.LowPart = number & 0xFFFFFFFF
    luid.HighPart = (number >> 32) & 0xFFFFFFFF
    return luid


def lookup_privilege_value(name):
    """Return the LUID for a privilege name as an integer."""
    luid = LUID()
    if not advapi32().LookupPrivilegeValueW(None, str(name), ctypes.byref(luid)):
        raise OSError(last_error(), "LookupPrivilegeValue failed")
    return luid_to_int(luid)


def lookup_privilege_name(luid):
    """Return the privilege name for a LUID."""
    if not isinstance(luid, LUID):
        luid = int_to_luid(luid)
    size = wintypes.DWORD(0)
    advapi32().LookupPrivilegeNameW(None, ctypes.byref(luid), None, ctypes.byref(size))
    buffer = ctypes.create_unicode_buffer(size.value + 1)
    if not advapi32().LookupPrivilegeNameW(None, ctypes.byref(luid), buffer,
                                           ctypes.byref(size)):
        raise OSError(last_error(), "LookupPrivilegeName failed")
    return buffer.value


def adjust_privilege(handle, luid_int, enabled):
    """Switch one privilege on or off. Returns ``(ok, error)``."""
    privileges = TOKEN_PRIVILEGES()
    privileges.PrivilegeCount = 1
    privileges.Privileges[0].Luid = int_to_luid(luid_int)
    privileges.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED if enabled else 0
    ctypes.set_last_error(0)
    ok = advapi32().AdjustTokenPrivileges(wintypes.HANDLE(int(handle)), False,
                                          ctypes.byref(privileges), 0, None, None)
    return bool(ok), last_error()


def integrity_rid(handle):
    """Return the RID of the token's mandatory integrity label."""
    buffer, _ = get_token_information(handle, TokenIntegrityLevel, 64)
    sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents.value
    count = ctypes.cast(sid_pointer + 1, ctypes.POINTER(ctypes.c_ubyte)).contents.value
    last = ctypes.cast(sid_pointer + 8 + (count - 1) * 4,
                       ctypes.POINTER(wintypes.DWORD)).contents.value
    return int(last)
