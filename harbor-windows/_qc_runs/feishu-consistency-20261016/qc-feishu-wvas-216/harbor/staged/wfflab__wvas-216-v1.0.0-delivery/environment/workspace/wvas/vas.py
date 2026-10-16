"""Virtual address space auditing for the wvas diagnostic collector.

The collector asks three questions about a target process:

``regions(pid)``
    Which parts of the virtual address space does the process have in use?

``file_backed_regions(pid)``
    Which of those parts are backed by a file on disk, and which file?

``modules(pid)``
    Which executable images are loaded, and where?

The answers are what the field engineers read when a machine reports
"something keeps the log file mapped" or "the process has no address space
left", so they have to describe the target process, not a snapshot of an
earlier call.
"""

import ctypes

from . import _winapi as w
from .errors import WVasError

PATH_BUFFER_CHARS = 260

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


def protection_name(protect):
    """Map a PAGE_* protection value onto its short textual name."""
    return _PROTECTION_NAMES.get(protect & 0xFF, "?")


def type_name(region_type):
    """Map a MEM_* region type onto its short textual name."""
    return _TYPE_NAMES.get(region_type, "private")


def _open_process(pid):
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise WVasError("pid must be a positive integer", kind="badarg", pid=pid)
    handle = w.OpenProcess(
        w.PROCESS_QUERY_INFORMATION | w.PROCESS_VM_READ, False, pid
    )
    if not handle:
        raise OSError(w.last_error(), "OpenProcess failed")
    return handle


def _mapped_path(handle, mbi):
    """Return the file name backing this region, if any."""
    if mbi.Type not in (w.MEM_IMAGE, w.MEM_MAPPED):
        return None
    buffer = ctypes.create_unicode_buffer(PATH_BUFFER_CHARS)
    written = w.GetMappedFileNameW(
        handle, ctypes.c_void_p(mbi.BaseAddress), buffer, PATH_BUFFER_CHARS
    )
    if not written:
        return ""
    return buffer.value


def regions(pid, include_reserved=True):
    """Return the regions of ``pid``'s virtual address space."""
    handle = _open_process(pid)
    try:
        result = []
        mbi = w.MEMORY_BASIC_INFORMATION()
        address = 0
        while address < 0x7FFFFFFFFFFF:
            written = w.VirtualQueryEx(
                handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi),
            )
            if not written:
                break
            if mbi.State == w.MEM_COMMIT:
                base_address = mbi.BaseAddress or 0
                result.append({
                    "base": base_address & 0xFFFFFFFF,
                    "size": mbi.RegionSize & 0xFFFFFFFF,
                    "state": "commit",
                    "type": type_name(mbi.Type),
                    "protect": protection_name(mbi.Protect),
                    "path": _mapped_path(handle, mbi),
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


def modules(pid):
    """Return the loaded executable images, lowest base address first."""
    return [
        {"path": item["path"], "base": item["base"], "size": item["size"]}
        for item in regions(pid)
        if item["image"]
    ]
