"""Shared fixtures for the held-out tests."""
import shutil

import pytest

import diskcache as dc


@pytest.fixture
def cache():
    """A fresh cache removed after the test."""
    with dc.Cache() as cache:
        yield cache
    shutil.rmtree(cache.directory, ignore_errors=True)
