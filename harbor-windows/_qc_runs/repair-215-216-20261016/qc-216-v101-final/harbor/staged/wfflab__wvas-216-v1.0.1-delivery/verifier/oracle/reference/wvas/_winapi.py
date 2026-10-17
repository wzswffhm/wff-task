"""ctypes bindings for the Win32 calls the auditor needs."""

import ctypes
import ctypes.wintypes as wt

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

# ---- access rights ---------------------------------------------------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

# ---- region state ----------------------------------------------------------
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_FREE = 0x10000

# ---- region type -----------------------------------------------------------
MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000
MEM_PRIVATE = 0x20000

# ---- page protection -------------------------------------------------------
PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100

# ---- module enumeration ----------------------------------------------------
# Enumerate every module of the target, including the ones the loader mapped
# from a share rather than from a mounted volume.
LIST_MODULES_ALL = 0x03

# ---- Win32 error codes -----------------------------------------------------
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87
ERROR_INVALID_HANDLE = 6

# Long paths do not fit in MAX_PATH; the device prefix of a mapped file name
# adds another 20-ish characters on top of the volume path.
MAX_PATH_CHARS = 32768
MAX_DEVICE_CHARS = 1024


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    """MEMORY_BASIC_INFORMATION as the 64-bit ABI defines it."""

    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


class MEMORY_BASIC_INFORMATION32(ctypes.Structure):
    """The 32-bit variant, used when the target is a WOW64 process."""

    _fields_ = [
        ("BaseAddress", wt.DWORD),
        ("AllocationBase", wt.DWORD),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", wt.DWORD),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


class MODULEINFO(ctypes.Structure):
    """MODULEINFO, as returned by GetModuleInformation."""

    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wt.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
OpenProcess.restype = wt.HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wt.HANDLE]
CloseHandle.restype = wt.BOOL

VirtualQueryEx = kernel32.VirtualQueryEx
VirtualQueryEx.argtypes = [
    wt.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
]
VirtualQueryEx.restype = ctypes.c_size_t

GetMappedFileNameW = psapi.GetMappedFileNameW
GetMappedFileNameW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
GetMappedFileNameW.restype = wt.DWORD

QueryDosDeviceW = kernel32.QueryDosDeviceW
QueryDosDeviceW.argtypes = [wt.LPCWSTR, wt.LPWSTR, wt.DWORD]
QueryDosDeviceW.restype = wt.DWORD

# The image inventory has to stand on its own: an image may be mapped from a
# share whose device name has no DOS equivalent, in which case the region walk
# cannot name it even though the image itself is perfectly loadable.
EnumProcessModulesEx = psapi.EnumProcessModulesEx
EnumProcessModulesEx.argtypes = [
    wt.HANDLE,
    ctypes.c_void_p,
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
    wt.DWORD,
]
EnumProcessModulesEx.restype = wt.BOOL

GetModuleFileNameExW = psapi.GetModuleFileNameExW
GetModuleFileNameExW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
GetModuleFileNameExW.restype = wt.DWORD

GetModuleInformation = psapi.GetModuleInformation
GetModuleInformation.argtypes = [
    wt.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MODULEINFO),
    wt.DWORD,
]
GetModuleInformation.restype = wt.BOOL


def last_error():
    return ctypes.get_last_error()
