"""Virtual address space auditing for the wvas diagnostic collector."""

import ctypes
import sys

from . import _winapi as w
from .errors import WVasError

MAX_PATH_CHARS = 32768
MAX_DEVICE_CHARS = 1024

_PROTECTION_NAMES = {
    w.PAGE_NOACCESS: "none",
    w.PAGE_READONLY: "r",
    w.PAGE_READWRITE: "rw",
    w.PAGE_WRITECOPY: "wc",
    w.PAGE_EXECUTE: "x",
    w.PAGE_EXECUTE_READ: "xr",
    w.PAGE_EXECUTE_READWRITE: "xrw",
    w.PAGE_EXECUTE_WRITECOPY: "xwc",
}

_TYPE_NAMES = {
    w.MEM_IMAGE: "image",
    w.MEM_MAPPED: "mapped",
    w.MEM_PRIVATE: "private",
}

_STATE_NAMES = {
    w.MEM_COMMIT: "commit",
    w.MEM_RESERVE: "reserve",
}


def protection_name(protect):
    """Map a PAGE_* protection value onto its short textual name."""
    return _PROTECTION_NAMES.get(protect & 0xFF, "?")


def type_name(region_type):
    """Map a MEM_* region type onto its short textual name."""
    return _TYPE_NAMES.get(region_type, "private")


def _require_windows():
    if sys.platform != "win32":
        raise WVasError(
            "the address space auditor only exists on Windows",
            kind="unsupported",
        )


def _open_process(pid):
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise WVasError("pid must be a positive integer", kind="badarg", pid=pid)
    handle = w.OpenProcess(
        w.PROCESS_QUERY_INFORMATION | w.PROCESS_VM_READ, False, pid
    )
    if handle:
        return handle
    error = w.last_error()
    if error == w.ERROR_INVALID_PARAMETER:
        raise WVasError("no such process", kind="no-such-process", pid=pid)
    if error == w.ERROR_ACCESS_DENIED:
        raise WVasError(
            "the process cannot be opened for reading",
            kind="access-denied",
            pid=pid,
        )
    raise WVasError(
        "OpenProcess failed with Win32 error %d" % error,
        kind="query-failed",
        pid=pid,
    )


def _dos_device_map():
    """Return {"\\DEVICE\\HARDDISKVOLUMEN": "C:"} for every mounted drive."""
    mapping = {}
    buffer = ctypes.create_unicode_buffer(MAX_DEVICE_CHARS)
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = letter + ":"
        if w.QueryDosDeviceW(drive, buffer, MAX_DEVICE_CHARS):
            target = buffer.value
            if target:
                mapping[target.upper()] = drive
    return mapping


def _to_dos_path(device_path):
    """Translate an NT device path into the DOS path a user can open."""
    if not device_path:
        return None
    path = device_path
    if path[:4].upper() == "\\??\\":
        path = path[4:]
    if path[:4] == "\\\\?\\":
        path = path[4:]
    if len(path) >= 2 and path[1] == ":":
        return path
    upper = path.upper()
    best = None
    for prefix, drive in _dos_device_map().items():
        if upper.startswith(prefix):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, drive)
    if best is not None:
        return best[1] + path[len(best[0]):]
    if upper.startswith("\\DEVICE\\MUP\\"):
        return "\\\\" + path[len("\\Device\\Mup\\"):]
    return None


def _mapped_path(handle, base_address):
    """Return the DOS path backing this region, or None when it is anonymous."""
    size = MAX_PATH_CHARS
    while size <= (1 << 22):
        buffer = ctypes.create_unicode_buffer(size)
        written = w.GetMappedFileNameW(
            handle, ctypes.c_void_p(base_address), buffer, size
        )
        if not written:
            return None
        if written < size - 1:
            return _to_dos_path(buffer.value)
        size *= 2
    return _to_dos_path(buffer.value)


def regions(pid, include_reserved=True):
    """Return the regions of ``pid``'s virtual address space.

    Every value is reported at its full 64-bit width and every file-backed
    region carries the DOS path of the file behind it.
    """
    _require_windows()
    handle = _open_process(pid)
    try:
        result = []
        mbi = w.MEMORY_BASIC_INFORMATION()
        address = 0
        limit = (1 << 47) - 1
        while address < limit:
            written = w.VirtualQueryEx(
                handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi),
            )
            if not written:
                break
            state = _STATE_NAMES.get(mbi.State)
            if state is not None and (state == "commit" or include_reserved):
                protect = mbi.Protect or mbi.AllocationProtect
                if mbi.State == w.MEM_RESERVE:
                    protect = mbi.AllocationProtect
                result.append({
                    "base": int(mbi.BaseAddress or 0),
                    "size": int(mbi.RegionSize),
                    "state": state,
                    "type": type_name(mbi.Type),
                    "protect": protection_name(protect),
                    "path": _mapped_path(handle, mbi.BaseAddress),
                    "image": mbi.Type == w.MEM_IMAGE,
                })
            next_address = (mbi.BaseAddress or 0) + mbi.RegionSize
            if next_address <= address:
                break
            address = next_address
        result.sort(key=lambda item: item["base"])
        return result
    finally:
        w.CloseHandle(handle)


def file_backed_regions(pid):
    """Return only the regions that have a file behind them."""
    return [item for item in regions(pid) if item["path"]]


def _module_path(handle, module):
    """Return the DOS path of a loaded module, growing the buffer as needed."""
    size = MAX_PATH_CHARS
    buffer = None
    while size <= (1 << 22):
        buffer = ctypes.create_unicode_buffer(size)
        written = w.GetModuleFileNameExW(
            handle, ctypes.c_void_p(module), buffer, size
        )
        if not written:
            return None
        if written < size - 1:
            return buffer.value or None
        size *= 2
    return (buffer.value or None) if buffer is not None else None


def modules(pid):
    """Return the loaded executable images, lowest base address first.

    The inventory is built from the loader's own module list rather than from
    the region walk: an image can be mapped from a share whose device name has
    no DOS equivalent, and the inventory still has to name it.
    """
    _require_windows()
    handle = _open_process(pid)
    try:
        needed = ctypes.c_ulong(0)
        if not w.EnumProcessModulesEx(
            handle, None, 0, ctypes.byref(needed), w.LIST_MODULES_ALL
        ):
            raise WVasError(
                "EnumProcessModulesEx failed with Win32 error %d" % w.last_error(),
                kind="query-failed",
                pid=pid,
            )
        count = needed.value // ctypes.sizeof(ctypes.c_void_p)
        if count <= 0:
            return []
        array = (ctypes.c_void_p * count)()
        if not w.EnumProcessModulesEx(
            handle, ctypes.byref(array), needed.value, ctypes.byref(needed),
            w.LIST_MODULES_ALL,
        ):
            raise WVasError(
                "EnumProcessModulesEx failed with Win32 error %d" % w.last_error(),
                kind="query-failed",
                pid=pid,
            )
        seen = set()
        result = []
        for index in range(count):
            module = array[index]
            if not module:
                continue
            path = _module_path(handle, module)
            if not path:
                continue
            key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            size = 0
            info = w.MODULEINFO()
            if w.GetModuleInformation(
                handle, ctypes.c_void_p(module), ctypes.byref(info),
                ctypes.sizeof(info),
            ):
                size = int(info.SizeOfImage)
            result.append({"path": path, "base": int(module), "size": size})
        result.sort(key=lambda item: item["base"])
        return result
    finally:
        w.CloseHandle(handle)
