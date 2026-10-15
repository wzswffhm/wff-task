"""Locate the ValueError the hidden suite hits while reading the token."""

import ctypes
import sys
from ctypes import wintypes

TokenPrivileges = 3
TOKEN_QUERY = 0x0008

advapi = ctypes.WinDLL("advapi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.HANDLE)]
advapi.OpenProcessToken.restype = wintypes.BOOL
advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
advapi.GetTokenInformation.restype = wintypes.BOOL
advapi.LookupPrivilegeNameW.restype = wintypes.BOOL
kernel32.GetCurrentProcess.restype = wintypes.HANDLE


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", ctypes.c_long)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


print("sizeof(LUID)                =", ctypes.sizeof(LUID))
print("sizeof(LUID_AND_ATTRIBUTES) =", ctypes.sizeof(LUID_AND_ATTRIBUTES))

handle = wintypes.HANDLE()
ok = advapi.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(handle))
print("OpenProcessToken ok =", bool(ok), "err =", ctypes.get_last_error())

needed = wintypes.DWORD(0)
advapi.GetTokenInformation(handle, TokenPrivileges, None, 0, ctypes.byref(needed))
print("needed bytes =", needed.value)

buf = ctypes.create_string_buffer(needed.value)
ok = advapi.GetTokenInformation(handle, TokenPrivileges, buf, needed.value, ctypes.byref(needed))
print("GetTokenInformation ok =", bool(ok), "returned =", needed.value)

count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
print("PrivilegeCount =", count)

base_int = ctypes.addressof(buf) + ctypes.sizeof(wintypes.DWORD)
print("base address offset =", ctypes.sizeof(wintypes.DWORD))

array = ctypes.cast(base_int, ctypes.POINTER(LUID_AND_ATTRIBUTES * count)).contents
first = array[0]
print("array[0].Luid.LowPart  =", first.Luid.LowPart, type(first.Luid.LowPart))
print("array[0].Luid.HighPart =", first.Luid.HighPart, type(first.Luid.HighPart))
print("array[0].Attributes    =", first.Attributes)

# what the old code did: int() on a bytes-ish value
probe = first.Luid.HighPart
print("int(HighPart) ->", end=" ")
try:
    print(int(probe))
except Exception as exc:
    print("RAISED %s: %s" % (type(exc).__name__, exc))

# now the name lookup, exactly as the suite does it
size = wintypes.DWORD(0)
advapi.LookupPrivilegeNameW(None, ctypes.byref(first.Luid), None, ctypes.byref(size))
print("LookupPrivilegeName size =", size.value)
name_buf = ctypes.create_unicode_buffer(size.value + 1)
ok = advapi.LookupPrivilegeNameW(None, ctypes.byref(first.Luid), name_buf, ctypes.byref(size))
print("LookupPrivilegeNameW ok =", bool(ok), "name =", name_buf.value)

# also try the raw byte slice the error message looked like
raw = ctypes.string_at(base_int, 8)
print("raw first 8 bytes =", raw)
print("int(raw) ->", end=" ")
try:
    print(int(raw))
except Exception as exc:
    print("RAISED %s: %s" % (type(exc).__name__, exc))

print("DIAG_DONE")
