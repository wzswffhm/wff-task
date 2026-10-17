"""Visible smoke tests for the wvas address space auditor.

These are the checks the collector team runs locally. They only describe the
shape of the answers, never the exact layout of a live process.
"""

import os

import pytest

import wvas


def test_regions_of_the_own_process_is_a_non_empty_list():
    regions = wvas.regions(os.getpid())
    assert isinstance(regions, list)
    assert regions


def test_region_records_have_the_documented_fields():
    item = wvas.regions(os.getpid())[0]
    assert set(item) == {
        "base", "size", "state", "type", "protect", "path", "image",
    }
    assert isinstance(item["base"], int) and item["base"] >= 0
    assert isinstance(item["size"], int) and item["size"] > 0
    assert item["state"] in ("commit", "reserve")
    assert item["type"] in ("image", "mapped", "private")
    assert isinstance(item["protect"], str)
    assert item["path"] is None or isinstance(item["path"], str)
    assert isinstance(item["image"], bool)


def test_regions_are_reported_in_ascending_order():
    bases = [item["base"] for item in wvas.regions(os.getpid())]
    assert bases == sorted(bases)


def test_file_backed_regions_are_a_subset_of_the_regions():
    regions = wvas.regions(os.getpid())
    backed = wvas.file_backed_regions(os.getpid())
    assert isinstance(backed, list)
    assert all(item["path"] for item in backed)
    keys = {(item["base"], item["size"]) for item in regions}
    assert all((item["base"], item["size"]) in keys for item in backed)


def test_include_reserved_false_only_reports_committed_memory():
    regions = wvas.regions(os.getpid(), include_reserved=False)
    assert all(item["state"] == "commit" for item in regions)


def test_modules_of_the_own_process_are_reported_in_ascending_order():
    modules = wvas.modules(os.getpid())
    assert isinstance(modules, list)
    assert modules
    for item in modules:
        assert isinstance(item["base"], int)
        assert item["path"]
    bases = [item["base"] for item in modules]
    assert bases == sorted(bases)


def test_a_negative_pid_is_rejected():
    with pytest.raises(wvas.WVasError) as caught:
        wvas.regions(-1)
    assert caught.value.kind == "badarg"


def test_protection_and_type_helpers_are_pure():
    assert wvas.protection_name(0x04) == "rw"
    assert wvas.protection_name(0x20) == "xr"
    assert wvas.type_name(0x1000000) == "image"
    assert wvas.type_name(0x40000) == "mapped"
    assert wvas.type_name(0x20000) == "private"
