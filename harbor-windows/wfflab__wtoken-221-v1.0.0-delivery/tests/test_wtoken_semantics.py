"""Hidden semantic suite for the wfflab__wtoken-221 Windows token contract.

This file is injected by the evaluation side and is never shipped in the task
package.  Every assertion that decides whether the candidate is right is backed
by a measurement the suite performs itself:

* it opens the process token with ``OpenProcessToken``,
* it reads the privilege array with ``GetTokenInformation(TokenPrivileges)`` and
  resolves names and identifiers with ``LookupPrivilegeName`` /
  ``LookupPrivilegeValue``,
* it drives ``AdjustTokenPrivileges`` **through the candidate** and then re-reads
  the attribute bits on its own handle,
* it reads ``TokenElevation``, ``TokenElevationType`` and ``TokenIntegrityLevel``
  directly.

The candidate never gets to describe its own result.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

import pytest

if os.name != "nt":
    pytest.skip(
        "the wtoken contract is a Windows token contract",
        allow_module_level=True,
    )

import wtoken as wtoken_package
from wtoken import (
    WTokenError,
    elevation,
    has_privilege,
    integrity_level,
    privilege_luid,
    privilege_name,
    privileges,
    set_privilege,
)

# --------------------------------------------------------------- Win32 layer

TOKEN_QUERY = 0x0008
TOKEN_ADJUST_PRIVILEGES = 0x0020

SE_PRIVILEGE_ENABLED = 0x00000002
SE_PRIVILEGE_ENABLED_BY_DEFAULT = 0x00000001
SE_PRIVILEGE_REMOVED = 0x00000004

TokenPrivileges = 3
TokenElevationType = 18
TokenElevation = 20
TokenIntegrityLevel = 25

ERROR_NOT_ALL_ASSIGNED = 1300

_advapi = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.HANDLE)]
_advapi.OpenProcessToken.restype = wintypes.BOOL
_advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
_advapi.GetTokenInformation.restype = wintypes.BOOL
_advapi.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, wintypes.LPVOID,
                                          wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
_advapi.AdjustTokenPrivileges.restype = wintypes.BOOL
_advapi.LookupPrivilegeNameW.restype = wintypes.BOOL
_advapi.LookupPrivilegeValueW.restype = wintypes.BOOL
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", ctypes.c_long)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD),
                ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def _open_token(access=TOKEN_QUERY):
    handle = wintypes.HANDLE()
    if not _advapi.OpenProcessToken(_kernel32.GetCurrentProcess(), access, ctypes.byref(handle)):
        raise OSError(ctypes.get_last_error(), "OpenProcessToken failed")
    return handle.value


def _close(handle):
    _kernel32.CloseHandle(wintypes.HANDLE(int(handle)))


def _lookup_name(luid):
    size = wintypes.DWORD(0)
    _advapi.LookupPrivilegeNameW(None, ctypes.byref(luid), None, ctypes.byref(size))
    buf = ctypes.create_unicode_buffer(size.value + 1)
    if not _advapi.LookupPrivilegeNameW(None, ctypes.byref(luid), buf, ctypes.byref(size)):
        raise OSError(ctypes.get_last_error(), "LookupPrivilegeName failed")
    return buf.value


def _lookup_value(name):
    luid = LUID()
    if not _advapi.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
        raise OSError(ctypes.get_last_error(), "LookupPrivilegeValue failed")
    return (luid.HighPart << 32) | luid.LowPart


def observed_privileges():
    """The token's privilege array as the operating system reports it.

    Returns ``{name: attributes}`` where the key is the privilege name and the
    value is the raw attributes DWORD.
    """
    handle = _open_token()
    try:
        needed = wintypes.DWORD(0)
        _advapi.GetTokenInformation(handle, TokenPrivileges, None, 0, ctypes.byref(needed))
        buf = ctypes.create_string_buffer(needed.value)
        if not _advapi.GetTokenInformation(handle, TokenPrivileges, buf, needed.value,
                                           ctypes.byref(needed)):
            raise OSError(ctypes.get_last_error(), "GetTokenInformation(TokenPrivileges) failed")
        count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
        base = ctypes.addressof(buf) + ctypes.sizeof(wintypes.DWORD)
        arr = ctypes.cast(base, ctypes.POINTER(LUID_AND_ATTRIBUTES * count)).contents
        table = {}
        for index in range(count):
            table[_lookup_name(arr[index].Luid)] = arr[index].Attributes
        return table
    finally:
        _close(handle)


def observed_enabled(name):
    """Whether the named privilege currently carries the enabled bit."""
    table = observed_privileges()
    if name not in table:
        return None
    return bool(table[name] & SE_PRIVILEGE_ENABLED)


def observed_elevated():
    handle = _open_token()
    try:
        value = wintypes.DWORD(0)
        needed = wintypes.DWORD(0)
        if not _advapi.GetTokenInformation(handle, TokenElevation, ctypes.byref(value),
                                           ctypes.sizeof(value), ctypes.byref(needed)):
            raise OSError(ctypes.get_last_error(), "GetTokenInformation(TokenElevation) failed")
        return bool(value.value)
    finally:
        _close(handle)


INTEGRITY_RID_NAMES = {
    0x0000: "untrusted",
    0x1000: "low",
    0x2000: "medium",
    0x2100: "medium plus",
    0x3000: "high",
    0x4000: "system",
    0x5000: "protected process",
}


def observed_integrity_rid():
    """The RID of the token's mandatory integrity label SID."""
    handle = _open_token()
    try:
        needed = wintypes.DWORD(0)
        _advapi.GetTokenInformation(handle, TokenIntegrityLevel, None, 0, ctypes.byref(needed))
        buf = ctypes.create_string_buffer(needed.value)
        if not _advapi.GetTokenInformation(handle, TokenIntegrityLevel, buf, needed.value,
                                           ctypes.byref(needed)):
            raise OSError(ctypes.get_last_error(), "GetTokenInformation(TokenIntegrityLevel) failed")
        # TOKEN_MANDATORY_LABEL { SID_AND_ATTRIBUTES { PSID Sid; DWORD Attributes; } }
        sid_pointer = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p)).contents.value
        # SID: Revision(1) SubAuthorityCount(1) IdentifierAuthority(6) SubAuthority[]
        count = ctypes.cast(sid_pointer + 1, ctypes.POINTER(ctypes.c_ubyte)).contents.value
        last = ctypes.cast(sid_pointer + 8 + (count - 1) * 4,
                           ctypes.POINTER(wintypes.DWORD)).contents.value
        return int(last)
    finally:
        _close(handle)


def _restore(name, attributes):
    """Put the privilege back the way the suite found it."""
    if attributes is None:
        return
    handle = _open_token(TOKEN_QUERY | TOKEN_ADJUST_PRIVILEGES)
    try:
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        luid = LUID()
        _advapi.LookupPrivilegeValueW(None, name, ctypes.byref(luid))
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = attributes
        _advapi.AdjustTokenPrivileges(handle, False, ctypes.byref(tp), 0, None, None)
    finally:
        _close(handle)


@pytest.fixture()
def togglable_privilege():
    """A privilege the token holds but which is currently switched off."""
    table = observed_privileges()
    candidates = sorted(n for n, a in table.items() if not (a & SE_PRIVILEGE_ENABLED))
    if not candidates:
        pytest.skip("this token has every privilege enabled; nothing to toggle")
    name = candidates[0]
    original = table[name]
    try:
        yield name
    finally:
        _restore(name, original)


@pytest.fixture()
def enabled_privilege():
    """A privilege the token holds and which is currently switched on."""
    table = observed_privileges()
    candidates = sorted(n for n, a in table.items() if a & SE_PRIVILEGE_ENABLED)
    if not candidates:
        pytest.skip("this token has no enabled privilege to observe")
    return candidates[0]


# ----------------------------------------------------- A. the inventory

def test_inventory_matches_the_token_exactly():
    external = observed_privileges()
    reported = privileges()
    assert set(reported) == set(external), (
        "the reported inventory differs from the token: missing=%s extra=%s"
        % (sorted(set(external) - set(reported)), sorted(set(reported) - set(external))))


def test_inventory_marks_disabled_privileges_as_disabled(togglable_privilege):
    name = togglable_privilege
    assert observed_enabled(name) is False, "fixture is not a disabled privilege"
    reported = privileges()
    assert name in reported, "a held-but-disabled privilege disappeared from the inventory"
    assert reported[name] is False, (
        "a held-but-disabled privilege was reported as enabled: this is the held-versus-enabled mix-up")


def test_inventory_marks_enabled_privileges_as_enabled(enabled_privilege):
    assert privileges()[enabled_privilege] is True


# ------------------------------------------- B. held is not the same as enabled

def test_a_disabled_privilege_is_still_held(togglable_privilege):
    name = togglable_privilege
    assert observed_enabled(name) is False
    assert has_privilege(name) is True, (
        "a privilege that is merely switched off must still be reported as held")


def test_held_and_enabled_disagree_for_a_disabled_privilege(togglable_privilege):
    name = togglable_privilege
    assert has_privilege(name) is True
    assert privileges()[name] is False, (
        "the two questions collapsed into one answer again")


# --------------------------------------- C. switching a privilege really works

def test_enabling_a_privilege_is_visible_to_the_system(togglable_privilege):
    name = togglable_privilege
    assert observed_enabled(name) is False
    set_privilege(name, True)
    assert observed_enabled(name) is True, (
        "the operating system does not see the privilege as enabled after the call")
    assert privileges()[name] is True, "the module's own report disagrees with the system"


def test_disabling_a_privilege_is_visible_to_the_system(enabled_privilege):
    name = enabled_privilege
    assert observed_enabled(name) is True
    set_privilege(name, False)
    assert observed_enabled(name) is False, (
        "the operating system still sees the privilege as enabled after the call")
    assert privileges()[name] is False, "the module's own report disagrees with the system"


def test_switching_round_trip_leaves_the_original_state(togglable_privilege):
    name = togglable_privilege
    set_privilege(name, True)
    assert observed_enabled(name) is True
    set_privilege(name, False)
    assert observed_enabled(name) is False


def test_set_privilege_rejects_a_privilege_the_token_does_not_hold():
    external = observed_privileges()
    invented = "SeNoSuchPrivilegeXYZ221"
    assert invented not in external
    with pytest.raises(WTokenError) as caught:
        set_privilege(invented, True)
    assert caught.value.kind in ("badarg", "unsupported", "os"), (
        "kind was %r" % (caught.value.kind,))


# ------------------------------------------------ D. names and identifiers

def test_luid_matches_the_system_for_every_held_privilege():
    mismatched = []
    for name in sorted(observed_privileges()):
        try:
            mine = int(privilege_luid(name))
        except WTokenError as exc:
            mismatched.append("%s raised %s" % (name, exc))
            continue
        if mine != _lookup_value(name):
            mismatched.append("%s: module=%d system=%d" % (name, mine, _lookup_value(name)))
    assert not mismatched, "identifiers do not match the system: %s" % mismatched[:5]


def test_name_and_luid_are_inverses(enabled_privilege):
    luid = privilege_luid(enabled_privilege)
    assert privilege_name(luid) == enabled_privilege


def test_privilege_name_round_trips_a_second_privilege():
    names = sorted(observed_privileges())
    if len(names) < 2:
        pytest.skip("need at least two privileges to round-trip")
    for name in names[:4]:
        assert privilege_name(privilege_luid(name)) == name


def test_unknown_privilege_name_is_rejected():
    with pytest.raises(WTokenError) as caught:
        privilege_luid("SeNoSuchPrivilegeXYZ221")
    assert caught.value.kind == "badarg"


def test_unknown_identifier_is_rejected():
    with pytest.raises(WTokenError) as caught:
        privilege_name(0x7FFFFFFF)
    assert caught.value.kind == "badarg"


def test_non_integer_identifier_is_rejected():
    with pytest.raises(WTokenError) as caught:
        privilege_name("not-an-identifier")
    assert caught.value.kind == "badarg"


# ------------------------------------ E. elevation and integrity

def test_elevation_matches_the_token():
    state = elevation()
    assert isinstance(state, dict)
    assert state.get("elevated") is observed_elevated(), (
        "the reported elevation does not match TokenElevation")


def test_integrity_level_names_the_token_level():
    rid = observed_integrity_rid()
    expected = INTEGRITY_RID_NAMES.get(rid)
    if expected is None:
        pytest.skip("unknown integrity RID 0x%x" % rid)
    reported = integrity_level()
    assert isinstance(reported, str) and reported
    assert reported.strip().lower() == expected, (
        "reported integrity %r but the token label is %r" % (reported, expected))


# --------------------------------------------------------- regression surface

def test_privileges_returns_a_plain_mapping():
    table = privileges()
    assert isinstance(table, dict)
    for name, enabled in table.items():
        assert isinstance(name, str) and name
        assert isinstance(enabled, bool)


def test_has_privilege_returns_a_boolean_for_an_invented_name():
    assert has_privilege("SeNoSuchPrivilegeXYZ221") is False


def _locate_smoke_suite():
    """Find the shipped smoke suite, wherever this copy of the file lives."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [os.path.join(here, "test_wtoken_basic.py")]
    package = globals().get("wtoken")
    if package is not None and getattr(package, "__file__", None):
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(package.__file__)))
        candidates.append(os.path.join(package_root, "tests", "test_wtoken_basic.py"))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def test_visible_smoke_suite_still_passes(tmp_path):
    """Every check in the shipped smoke suite must still hold.

    The suite is executed in this process rather than in a nested interpreter:
    the verdict is identical, and a grading harness that redirects the temporary
    directory cannot turn this check into a spurious failure.
    """
    import importlib.util
    import inspect

    smoke = _locate_smoke_suite()
    assert smoke is not None, (
        "the visible smoke suite could not be located next to this file or in the "
        "candidate workspace")

    spec = importlib.util.spec_from_file_location("wtoken_visible_smoke", smoke)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    failures = []
    for name in sorted(dir(module)):
        if not name.startswith("test_"):
            continue
        function = getattr(module, name)
        if not callable(function):
            continue
        try:
            if inspect.signature(function).parameters:
                function(tmp_path)
            else:
                function()
        except Exception as exc:  # noqa: BLE001 - the report is the point
            failures.append("%s: %s: %s" % (name, type(exc).__name__, exc))

    assert not failures, (
        "the visible smoke suite no longer passes:\n  " + "\n  ".join(failures))
