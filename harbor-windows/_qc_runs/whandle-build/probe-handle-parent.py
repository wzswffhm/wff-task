"""Probe parent: can a child be given exactly one inherited handle?

Pure ASCII. Runs inside the Windows Server Core container.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
CREATE_ALWAYS = 2
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

HANDLE_FLAG_INHERIT = 0x00000001

EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
STARTF_USESTDHANDLES = 0x00000100

k = ctypes.WinDLL("kernel32", use_last_error=True)

k.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
                         wintypes.LPVOID, wintypes.DWORD]
k.CreatePipe.restype = wintypes.BOOL
k.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
k.SetHandleInformation.restype = wintypes.BOOL
k.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k.GetHandleInformation.restype = wintypes.BOOL
k.CloseHandle.argtypes = [wintypes.HANDLE]
k.CloseHandle.restype = wintypes.BOOL
k.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                       ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k.ReadFile.restype = wintypes.BOOL
k.InitializeProcThreadAttributeList.argtypes = [wintypes.LPVOID, wintypes.DWORD,
                                                wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
k.InitializeProcThreadAttributeList.restype = wintypes.BOOL
k.UpdateProcThreadAttribute.argtypes = [wintypes.LPVOID, wintypes.DWORD, ctypes.c_size_t,
                                        wintypes.LPVOID, ctypes.c_size_t,
                                        wintypes.LPVOID, wintypes.LPVOID]
k.UpdateProcThreadAttribute.restype = wintypes.BOOL
k.DeleteProcThreadAttributeList.argtypes = [wintypes.LPVOID]
k.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
                             wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
                             wintypes.LPVOID, wintypes.LPVOID]
k.CreateProcessW.restype = wintypes.BOOL
k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k.WaitForSingleObject.restype = wintypes.DWORD
k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
k.GetExitCodeProcess.restype = wintypes.BOOL


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
                ("hStdError", wintypes.HANDLE)]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", wintypes.LPVOID)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


def err():
    return ctypes.get_last_error()


def make_pipe():
    r = wintypes.HANDLE()
    w = wintypes.HANDLE()
    if not k.CreatePipe(ctypes.byref(r), ctypes.byref(w), None, 0):
        raise OSError(err(), "CreatePipe failed")
    return r, w


def inherit_flag(h):
    flags = wintypes.DWORD(0)
    if not k.GetHandleInformation(h, ctypes.byref(flags)):
        raise OSError(err(), "GetHandleInformation failed")
    return bool(flags.value & HANDLE_FLAG_INHERIT)


def set_inherit(h, on=True):
    mask = HANDLE_FLAG_INHERIT
    flags = HANDLE_FLAG_INHERIT if on else 0
    if not k.SetHandleInformation(h, mask, flags):
        raise OSError(err(), "SetHandleInformation failed")


def spawn(child_py, child_script, extra_args, restrict_to, use_list):
    """Run the child. restrict_to = list of handles to hand over when use_list."""
    si = STARTUPINFOEXW()
    si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
    si.StartupInfo.dwFlags = STARTF_USESTDHANDLES
    si.StartupInfo.hStdInput = None
    si.StartupInfo.hStdOutput = None
    si.StartupInfo.hStdError = None

    size = ctypes.c_size_t(0)
    k.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    buf = ctypes.create_string_buffer(size.value)
    if not k.InitializeProcThreadAttributeList(buf, 1, 0, ctypes.byref(size)):
        raise OSError(err(), "InitializeProcThreadAttributeList failed")
    si.lpAttributeList = ctypes.cast(buf, wintypes.LPVOID)

    if use_list:
        n = len(restrict_to)
        arr = (wintypes.HANDLE * n)(*restrict_to)
        ok = k.UpdateProcThreadAttribute(si.lpAttributeList, 0,
                                         PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                         ctypes.cast(arr, wintypes.LPVOID),
                                         ctypes.sizeof(arr), None, None)
        if not ok:
            raise OSError(err(), "UpdateProcThreadAttribute failed")

    cmdline = ('"%s" "%s" %s' % (child_py, child_script, extra_args))
    cmd = ctypes.create_unicode_buffer(cmdline)
    flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT
    pi = PROCESS_INFORMATION()
    ok = k.CreateProcessW(None, cmd, None, None, True, flags, None, None,
                          ctypes.byref(si), ctypes.byref(pi))
    if not ok:
        k.DeleteProcThreadAttributeList(si.lpAttributeList)
        raise OSError(err(), "CreateProcessW failed")

    k.WaitForSingleObject(pi.hProcess, 60000)
    code = wintypes.DWORD(0)
    k.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    k.CloseHandle(pi.hThread)
    k.CloseHandle(pi.hProcess)
    k.DeleteProcThreadAttributeList(si.lpAttributeList)
    return code.value


def read_all(h):
    chunks = []
    buf = ctypes.create_string_buffer(4096)
    got = wintypes.DWORD(0)
    while k.ReadFile(h, buf, 4096, ctypes.byref(got), None) and got.value:
        chunks.append(buf.raw[:got.value])
    return b"".join(chunks)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    child = os.path.join(here, "probe-handle-child.py")
    py = sys.executable

    print("=== 1. handle inherit flags after CreatePipe")
    r1, w1 = make_pipe()
    print("   default: read inherit=%s write inherit=%s (expect False/False)"
          % (inherit_flag(r1), inherit_flag(w1)))
    set_inherit(w1, True)
    print("   after SetHandleInformation(write, INHERIT): write inherit=%s" % inherit_flag(w1))

    print("=== 2. child WITHOUT a handle list (plain bInheritHandles=TRUE)")
    r2, w2 = make_pipe()
    r3, w3 = make_pipe()
    set_inherit(w2, True)
    set_inherit(w3, True)
    code = spawn(py, child, "%d %d" % (w2.value, w3.value), [w2], use_list=False)
    print("   child exit=%s" % code)
    # Close our own copies of the write ends, otherwise ReadFile never sees EOF.
    k.CloseHandle(w2)
    k.CloseHandle(w3)
    data = read_all(r2).decode("utf-8", "replace") + read_all(r3).decode("utf-8", "replace")
    for line in data.splitlines():
        print("   child says: %s" % line)

    print("=== 3. child WITH PROC_THREAD_ATTRIBUTE_HANDLE_LIST = [w5] only")
    r5, w5 = make_pipe()
    r6, w6 = make_pipe()
    set_inherit(w5, True)
    set_inherit(w6, True)
    code = spawn(py, child, "%d %d" % (w5.value, w6.value), [w5], use_list=True)
    print("   child exit=%s" % code)
    k.CloseHandle(w5)
    k.CloseHandle(w6)
    data = read_all(r5).decode("utf-8", "replace") + read_all(r6).decode("utf-8", "replace")
    for line in data.splitlines():
        print("   child says: %s" % line)

    print("=== 4. handle values: are they preserved into the child?")
    print("   w5=%d w6=%d (child was told these exact values)" % (w5.value, w6.value))

    for h in (r1, w1, r2, r3, r5, r6):
        k.CloseHandle(h)
    print("PROBE_HANDLE_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
