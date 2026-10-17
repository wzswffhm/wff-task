"""Probe suite: every case fails during fixture setup.

This is the reviewer probe for "an independent fixture raises in setup":
pytest reports outcome="error" for every case, so the run carries no
information about the candidate and must be INVALID, never a 0.
"""
import pytest


@pytest.fixture(autouse=True)
def infrastructure_fault():
    raise RuntimeError("simulated infrastructure fault during setup")

def test_region_addresses_are_64_bit():
    pass

def test_region_sizes_are_64_bit():
    pass

def test_reserved_regions_are_reported():
    pass

def test_file_mapping_path_is_a_dos_path():
    pass

def test_device_paths_are_translated():
    pass

def test_anonymous_mapping_has_no_path():
    pass

def test_missing_process_is_classified():
    pass

def test_modules_are_deduplicated():
    pass

def test_regions_are_sorted_by_base():
    pass

def test_region_records_are_well_formed():
    pass

def test_own_process_reports_image_regions():
    pass

def test_file_backed_regions_are_a_subset():
    pass

def test_include_reserved_false_only_reports_committed_memory():
    pass

def test_negative_pid_is_rejected():
    pass

def test_modules_are_sorted_by_base():
    pass

def test_visible_smoke_suite_still_passes():
    pass
