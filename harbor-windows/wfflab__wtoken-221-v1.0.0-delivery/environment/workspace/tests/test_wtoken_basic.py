"""Smoke tests for the wtoken public API.

These are the tests that run while the deployment checker is being developed.
"""

import sys

import pytest

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


def test_privileges_returns_a_mapping_of_names_to_booleans():
    table = privileges()
    assert isinstance(table, dict)
    assert table, "the token always holds at least one privilege"
    for name, enabled in table.items():
        assert isinstance(name, str) and name
        assert isinstance(enabled, bool)


def test_has_privilege_returns_a_boolean():
    value = has_privilege("SeShutdownPrivilege")
    assert isinstance(value, bool)


def test_has_privilege_reports_false_for_an_invented_name():
    assert has_privilege("SeNoSuchPrivilegeMadeUp") is False


def test_set_privilege_rejects_an_unknown_name():
    with pytest.raises(WTokenError) as caught:
        set_privilege("SeNoSuchPrivilegeMadeUp", True)
    assert caught.value.kind in WTokenError.KINDS


def test_set_privilege_rejects_an_empty_name():
    with pytest.raises(WTokenError) as caught:
        set_privilege("", True)
    assert caught.value.kind in WTokenError.KINDS


def test_privilege_luid_rejects_an_unknown_name():
    with pytest.raises(WTokenError) as caught:
        privilege_luid("SeNoSuchPrivilegeMadeUp")
    assert caught.value.kind == "badarg"


def test_privilege_name_rejects_a_non_integer():
    with pytest.raises(WTokenError) as caught:
        privilege_name("not-an-identifier")
    assert caught.value.kind == "badarg"


def test_privilege_name_rejects_an_out_of_range_identifier():
    with pytest.raises(WTokenError) as caught:
        privilege_name(10 ** 9)
    assert caught.value.kind == "badarg"


def test_elevation_returns_a_mapping_with_the_documented_keys():
    state = elevation()
    assert isinstance(state, dict)
    assert set(state) >= {"elevated", "type"}
    assert isinstance(state["elevated"], bool)
    assert isinstance(state["type"], str)


def test_integrity_level_returns_a_string():
    level = integrity_level()
    assert isinstance(level, str)


def test_error_carries_a_known_kind():
    with pytest.raises(WTokenError) as caught:
        set_privilege("SeNoSuchPrivilegeMadeUp")
    assert caught.value.kind in WTokenError.KINDS
    assert "SeNoSuchPrivilegeMadeUp" in str(caught.value)
