"""ctypes bindings for the Win32 calls the wspawn contract needs.

Everything the module does to a helper process passes through this file: the
inherit flag travels over ``SetHandleInformation`` / ``GetHandleInformation``,
the object class comes from ``GetFileType``, and the process is created with an
extended ``STARTUPINFO`` whose attribute list names exactly the handles that are
allowed to cross the boundary.
"""

import ctypes
import os
from ctypes import wintypes

# ---- access and sharing -----------------------------------------------------
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007

# ---- creation dispositions --------------------------------------------------
CREATE_ALWAYS = 2
OPEN_EXISTING = 3

# ---- attributes and flags ---------------------------------------------------
FILE_ATTRIBUTE_NORMAL = 0x00000080
HANDLE_FLAG_INHERIT = 0x00000001

# ---- GetFileType values -----------------------------------------------------
FILE_TYPE_UNKNOWN = 0x0000
FILE_TYPE_DISK = 0x00000001
FILE_TYPE_CHAR = 0x00000002
FILE_TYPE_PIPE = 0x00000003
FILE_TYPE_REMOTE = 0x00008000

# ---- process creation -------------------------------------------------------
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
STARTF_USESTDHANDLES = 0x00000100
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002

# ---- return / error codes ---------------------------------------------------
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
STILL_ACTIVE = 259

ERROR_INVALID_PARAMETER = 87
ERROR_INVALID_HANDLE = 6
ERROR_NOT_SUPPORTED = 50
UNSUPPORTED_ERRORS = (ERROR_INVALID_PARAMETER, ERROR_INVALID_HANDLE, ERROR_NOT_SUPPORTED)

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_IS_WINDOWS = os.name == "nt"

_kernel32 = None


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", wintypes.LPVOID)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def kind_for_error(error):
    """Map a Win32 error code onto the :class:`WSpawnError` taxonomy."""
    if error in UNSUPPORTED_ERRORS:
        return "unsupported"
    return "os"


def _declare(kernel32):
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetHandleInformation.restype = wintypes.BOOL
    kernel32.GetFileType.argtypes = [wintypes.HANDLE]
    kernel32.GetFileType.restype = wintypes.DWORD
    kernel32.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
                                    wintypes.LPVOID, wintypes.DWORD]
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.HANDLE]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        wintypes.LPVOID, wintypes.DWORD, ctypes.c_size_t, wintypes.LPVOID,
        ctypes.c_size_t, wintypes.LPVOID, wintypes.LPVOID]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [wintypes.LPVOID]
    kernel32.DeleteProcThreadAttributeList.restype = None
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
        wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        wintypes.LPVOID, wintypes.LPVOID]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL


def kernel32():
    """Load (once) and return the declared kernel32 entry points."""
    global _kernel32
    if _kernel32 is None:
        if not _IS_WINDOWS:
            raise OSError("the Win32 process API is only available on Windows")
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        _declare(dll)
        _kernel32 = dll
    return _kernel32


def last_error():
    return ctypes.get_last_error()


# ---- handles ----------------------------------------------------------------

def close(handle):
    """Close an object handle; ignore an already-invalid one."""
    if handle in (None, 0, INVALID_HANDLE_VALUE):
        return
    kernel32().CloseHandle(wintypes.HANDLE(int(handle)))


def set_inherit(handle, enabled=True):
    """Set or clear ``HANDLE_FLAG_INHERIT``. Returns ``(ok, error)``."""
    mask = HANDLE_FLAG_INHERIT
    flags = HANDLE_FLAG_INHERIT if enabled else 0
    ok = kernel32().SetHandleInformation(wintypes.HANDLE(int(handle)), mask, flags)
    return bool(ok), last_error()


def get_inherit(handle):
    """Read ``HANDLE_FLAG_INHERIT``. Returns ``(inherit, ok, error)``."""
    flags = wintypes.DWORD(0)
    ok = kernel32().GetHandleInformation(wintypes.HANDLE(int(handle)), ctypes.byref(flags))
    return bool(flags.value & HANDLE_FLAG_INHERIT), bool(ok), last_error()


def file_type(handle):
    """Return the ``GetFileType`` value for an object handle."""
    return int(kernel32().GetFileType(wintypes.HANDLE(int(handle))))


def create_pipe():
    read_end = wintypes.HANDLE()
    write_end = wintypes.HANDLE()
    if not kernel32().CreatePipe(ctypes.byref(read_end), ctypes.byref(write_end), None, 0):
        raise OSError(last_error(), "CreatePipe failed")
    return read_end.value, write_end.value


def write_all(handle, blob):
    """Write ``blob`` to an object handle. Returns ``(ok, written, error)``."""
    if not blob:
        return True, 0, 0
    written = wintypes.DWORD(0)
    ok = kernel32().WriteFile(wintypes.HANDLE(int(handle)), blob, len(blob),
                              ctypes.byref(written), None)
    return bool(ok), int(written.value), last_error()


def read_some(handle, size=4096):
    """Read up to ``size`` bytes. Returns ``(data, ok, error)``."""
    buf = ctypes.create_string_buffer(size)
    got = wintypes.DWORD(0)
    ok = kernel32().ReadFile(wintypes.HANDLE(int(handle)), buf, size, ctypes.byref(got), None)
    return buf.raw[: got.value], bool(ok), last_error()


# ---- creating a child with an explicit handle list --------------------------

def create_process(argv, inherit, stdout_handle=None, stderr_handle=None, stdin_handle=None):
    """Create a child process that inherits exactly ``inherit`` (plus std handles).

    Returns ``(process_handle, thread_handle, pid, error)``; on failure the
    handles are ``None`` and ``error`` carries the Win32 code.
    """
    k = kernel32()
    si = STARTUPINFOEXW()
    si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
    if stdout_handle or stderr_handle or stdin_handle:
        si.StartupInfo.dwFlags = STARTF_USESTDHANDLES
        si.StartupInfo.hStdInput = wintypes.HANDLE(int(stdin_handle)) if stdin_handle else None
        si.StartupInfo.hStdOutput = wintypes.HANDLE(int(stdout_handle)) if stdout_handle else None
        si.StartupInfo.hStdError = wintypes.HANDLE(int(stderr_handle)) if stderr_handle else None

    size = ctypes.c_size_t(0)
    k.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    if not k.InitializeProcThreadAttributeList(buffer, 1, 0, ctypes.byref(size)):
        return None, None, None, last_error()
    si.lpAttributeList = ctypes.cast(buffer, wintypes.LPVOID)

    handles = [int(item) for item in inherit]
    array = None
    if handles:
        array = (wintypes.HANDLE * len(handles))(*handles)
        ok = k.UpdateProcThreadAttribute(
            si.lpAttributeList, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            ctypes.cast(array, wintypes.LPVOID), ctypes.sizeof(array), None, None)
        if not ok:
            error = last_error()
            k.DeleteProcThreadAttributeList(si.lpAttributeList)
            return None, None, None, error

    command = ctypes.create_unicode_buffer(subprocess_list2cmdline(argv))
    flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT
    info = PROCESS_INFORMATION()
    ok = k.CreateProcessW(None, command, None, None, True, flags, None, None,
                          ctypes.byref(si), ctypes.byref(info))
    error = last_error()
    k.DeleteProcThreadAttributeList(si.lpAttributeList)
    if not ok:
        return None, None, None, error
    return info.hProcess, info.hThread, int(info.dwProcessId), 0


def subprocess_list2cmdline(argv):
    """Build a Windows command line from an argument vector.

    The MSVCRT rules are used: arguments are quoted only when they contain a
    space or a quote, and backslashes before a quote are doubled.
    """
    parts = []
    for arg in argv:
        text = str(arg)
        if text and not any(ch in text for ch in ' \t"'):
            parts.append(text)
            continue
        out = ['"']
        backslashes = 0
        for ch in text:
            if ch == '\\':
                backslashes += 1
                continue
            if ch == '"':
                out.append('\\' * (backslashes * 2 + 1))
                out.append('"')
                backslashes = 0
                continue
            out.append('\\' * backslashes)
            backslashes = 0
            out.append(ch)
        out.append('\\' * (backslashes * 2))
        out.append('"')
        parts.append(''.join(out))
    return ' '.join(parts)


def wait(process_handle, timeout_ms):
    """Wait for a process handle. Returns the ``WaitForSingleObject`` value."""
    return int(kernel32().WaitForSingleObject(wintypes.HANDLE(int(process_handle)), timeout_ms))


def exit_code(process_handle):
    code = wintypes.DWORD(0)
    if not kernel32().GetExitCodeProcess(wintypes.HANDLE(int(process_handle)), ctypes.byref(code)):
        raise OSError(last_error(), "GetExitCodeProcess failed")
    return int(code.value)


def terminate(process_handle):
    ok = kernel32().TerminateProcess(wintypes.HANDLE(int(process_handle)), 1)
    return bool(ok), last_error()


def close_thread(thread_handle):
    close(thread_handle)
