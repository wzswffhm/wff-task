"""Probe: what can a process learn and change about its own token?

Runs inside the Windows Server Core container. Pure ASCII.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

TOKEN_QUERY = 0x0008
TOKEN_ADJUST_PRIVILEGES = 0x0020
SE_PRIVILEGE_ENABLED = 0x00000002
SE_PRIVILEGE_ENABLED_BY_DEFAULT = 0x00000001
SE_PRIVILEGE_REMOVED = 0x00000004

TokenUser = 1
TokenPrivileges = 3
TokenElevation = 20
TokenElevationType = 18
TokenIntegrityLevel = 25
TokenGroups = 2

ERROR_NOT_ALL_ASSIGNED = 1300

advapi = ctypes.WinDLL("advapi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi.OpenProcessToken.restype = wintypes.BOOL
advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
advapi.GetTokenInformation.restype = wintypes.BOOL
advapi.LookupPrivilegeNameW.restype = wintypes.BOOL
advapi.LookupPrivilegeValueW.restype = wintypes.BOOL
advapi.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, wintypes.LPVOID,
                                         wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
advapi.AdjustTokenPrivileges.restype = wintypes.BOOL
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", ctypes.c_long)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def err():
    return ctypes.get_last_error()


def open_token(access=TOKEN_QUERY):
    handle = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel32.GetCurrentProcess(), access, ctypes.byref(handle)):
        raise OSError(err(), "OpenProcessToken failed")
    return handle


def privilege_name(luid):
    size = wintypes.DWORD(0)
    advapi.LookupPrivilegeNameW(None, ctypes.byref(luid), None, ctypes.byref(size))
    buf = ctypes.create_unicode_buffer(size.value + 1)
    if not advapi.LookupPrivilegeNameW(None, ctypes.byref(luid), buf, ctypes.byref(size)):
        return "?"
    return buf.value


def list_privileges(token):
    needed = wintypes.DWORD(0)
    advapi.GetTokenInformation(token, TokenPrivileges, None, 0, ctypes.byref(needed))
    buf = ctypes.create_string_buffer(needed.value)
    if not advapi.GetTokenInformation(token, TokenPrivileges, buf, needed.value, ctypes.byref(needed)):
        raise OSError(err(), "GetTokenInformation(TokenPrivileges) failed")
    count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
    arr = ctypes.cast(ctypes.addressof(buf) + ctypes.sizeof(wintypes.DWORD),
                      ctypes.POINTER(LUID_AND_ATTRIBUTES * count)).contents
    out = []
    for i in range(count):
        out.append((privilege_name(arr[i].Luid), arr[i].Attributes))
    return out


def main():
    print("=== 1. token open + privilege enumeration")
    token = open_token()
    privs = list_privileges(token)
    print("   privilege count = %d" % len(privs))
    enabled = [n for n, a in privs if a & SE_PRIVILEGE_ENABLED]
    print("   enabled now     = %d" % len(enabled))
    for name, attr in privs[:8]:
        print("     %-40s attr=0x%08x" % (name, attr))
    print("   more...")

    print("=== 2. does LookupPrivilegeValueW resolve a known name?")
    luid = LUID()
    ok = advapi.LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid))
    print("   SeShutdownPrivilege ok=%s luid=%d:%d err=%d" % (bool(ok), luid.LowPart, luid.HighPart, err()))

    print("=== 3. can we adjust privileges? (disable then re-enable SeShutdownPrivilege if present)")
    names = dict((n, a) for n, a in privs)
    have = "SeShutdownPrivilege" in names
    print("   SeShutdownPrivilege present in token: %s" % have)
    if have:
        token2 = open_token(TOKEN_QUERY | TOKEN_ADJUST_PRIVILEGES)
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = 0
        ctypes.set_last_error(0)
        ok = advapi.AdjustTokenPrivileges(token2, False, ctypes.byref(tp), 0, None, None)
        e = err()
        print("   disable -> ok=%s err=%d (1300 = not all assigned)" % (bool(ok), e))
        after = dict(list_privileges(token2))
        print("   SeShutdownPrivilege attr after disable = 0x%08x" % after.get("SeShutdownPrivilege", 0))
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        ctypes.set_last_error(0)
        ok = advapi.AdjustTokenPrivileges(token2, False, ctypes.byref(tp), 0, None, None)
        print("   enable  -> ok=%s err=%d" % (bool(ok), err()))
        after2 = dict(list_privileges(token2))
        print("   SeShutdownPrivilege attr after enable  = 0x%08x" % after2.get("SeShutdownPrivilege", 0))
        kernel32.CloseHandle(token2)

    print("=== 4. elevation / integrity level")
    for cls, label in ((TokenElevation, "TokenElevation"), (TokenElevationType, "TokenElevationType")):
        buf = wintypes.DWORD(0)
        needed = wintypes.DWORD(0)
        ok = advapi.GetTokenInformation(token, cls, ctypes.byref(buf),
                                        ctypes.sizeof(buf), ctypes.byref(needed))
        print("   %-18s ok=%s value=%d" % (label, bool(ok), buf.value))

    il = ctypes.create_string_buffer(64)
    needed = wintypes.DWORD(0)
    ok = advapi.GetTokenInformation(token, TokenIntegrityLevel, il, 64, ctypes.byref(needed))
    print("   TokenIntegrityLevel ok=%s needed=%d" % (bool(ok), needed.value))

    kernel32.CloseHandle(token)

    print("=== 5. what does whoami say (independent cross-check)")
    for args in (["whoami", "/priv"], ["whoami", "/user"], ["whoami", "/groups"]):
        p = subprocess.run(args, capture_output=True, text=True)
        first = (p.stdout or p.stderr or "").strip().splitlines()
        print("   %s -> exit=%d lines=%d" % (" ".join(args), p.returncode, len(first)))
        for line in first[:4]:
            print("       %s" % line.strip()[:110])

    print("=== 6. can we create a process with a modified token? (CreateProcessAsUser needs a privilege)")
    print("   SeAssignPrimaryTokenPrivilege present: %s" % ("SeAssignPrimaryTokenPrivilege" in names))
    print("   SeIncreaseQuotaPrivilege present    : %s" % ("SeIncreaseQuotaPrivilege" in names))
    print("   SeDebugPrivilege present            : %s" % ("SeDebugPrivilege" in names))
    print("   SeBackupPrivilege present           : %s" % ("SeBackupPrivilege" in names))
    print("   SeRestorePrivilege present          : %s" % ("SeRestorePrivilege" in names))
    print("   SeTakeOwnershipPrivilege present    : %s" % ("SeTakeOwnershipPrivilege" in names))

    print("PROBE_TOKEN_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
