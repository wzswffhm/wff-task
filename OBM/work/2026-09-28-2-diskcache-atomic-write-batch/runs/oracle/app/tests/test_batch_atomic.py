"""Behavioural tests for staged multi-key write batches.

Every test here exercises observable cache behaviour through the public API.
None of them refer to internal tables, private functions or file names.
"""
import os
import subprocess
import sys
import textwrap
import warnings

import pytest

from diskcache import Cache


def value_files(directory):
    """Every file below the cache directory, excluding the database itself."""
    names = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            path = os.path.join(root, name)
            if os.path.basename(path) != 'cache.db':
                names.append(path)
    return names


def unknown_file_warnings(cache):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        cache.check()
    return [str(item.message) for item in caught
            if 'unknown' in str(item.message).lower()]


CRASH_CHILD = textwrap.dedent(
    """
    import os, sys
    sys.path.insert(0, sys.argv[2])
    from diskcache import Cache
    cache = Cache(sys.argv[1])
    with cache.batch():
        cache['crashed'] = 'payload'
        cache['also-crashed'] = 'second'
        os._exit(9)
    """
)


def test_batch_commits_every_write_at_once(cache):
    with cache.batch():
        cache['alpha'] = 1
        cache['beta'] = 2

    assert cache['alpha'] == 1
    assert cache['beta'] == 2
    assert len(cache) == 2


def test_batch_is_invisible_to_other_handles_before_commit(cache):
    other = Cache(cache.directory)

    with cache.batch():
        cache['staged'] = 'value'
        assert other.get('staged') is None
        assert 'staged' not in other
        assert len(other) == 0

    assert other.get('staged') == 'value'
    assert len(other) == 1


def test_batch_supports_read_your_writes(cache):
    cache['existing'] = 'old'

    with cache.batch():
        cache['existing'] = 'new'
        cache['fresh'] = 'added'
        assert cache['existing'] == 'new'
        assert cache['fresh'] == 'added'
        assert len(cache) == 2


def test_batch_rollback_discards_every_write(cache):
    cache['keep'] = 'committed'

    with pytest.raises(RuntimeError):
        with cache.batch():
            cache['temporary'] = 'value'
            cache.delete('keep')
            assert 'keep' not in cache
            raise RuntimeError('discard')

    assert cache.get('temporary') is None
    assert cache['keep'] == 'committed'
    assert len(cache) == 1


def test_batch_rollback_leaves_no_files_behind(cache):
    cache['keep'] = 'committed'
    before = len(value_files(cache.directory))

    with pytest.raises(RuntimeError):
        with cache.batch():
            cache['temporary'] = 'value'
            raise RuntimeError('discard')

    assert len(value_files(cache.directory)) == before
    assert not unknown_file_warnings(cache)


def test_batch_last_write_wins_for_one_key(cache):
    cache['key'] = 'committed'

    with cache.batch():
        cache['key'] = 'first'
        cache['key'] = 'second'
        cache.delete('key')
        cache['key'] = 'third'

    assert cache['key'] == 'third'
    assert len(cache) == 1


def test_batch_delete_then_no_reset_removes_key(cache):
    cache['gone'] = 'committed'

    with cache.batch():
        cache.delete('gone')

    assert cache.get('gone') is None
    assert len(cache) == 0


def test_batch_add_respects_staged_state(cache):
    with cache.batch():
        assert cache.add('only', 1) is True
        assert cache.add('only', 2) is False
        assert cache['only'] == 1

    assert cache.add('only', 3) is False
    assert cache['only'] == 1


def test_batch_accepts_expire_only_after_commit(cache):
    with cache.batch():
        cache.set('short', 'value', expire=0.3)
        assert cache.get('short') == 'value'

    assert cache.get('short') == 'value'
    import time
    time.sleep(0.5)
    assert cache.get('short') is None


def test_batch_tagged_keys_join_tag_eviction_after_commit(cache):
    cache.set('plain', 'value', tag='group')

    with cache.batch():
        cache.set('staged', 'value', tag='group')

    assert cache.get('staged') == 'value'
    assert cache.evict('group') >= 2
    assert cache.get('staged') is None
    assert cache.get('plain') is None


def test_batch_rejects_nesting(cache):
    with pytest.raises(RuntimeError):
        with cache.batch():
            with cache.batch():
                cache['nope'] = 1

    assert cache.get('nope') is None


def test_batch_rejects_operations_that_cannot_be_staged(cache):
    with pytest.raises(RuntimeError):
        with cache.batch():
            cache.clear()

    with pytest.raises(RuntimeError):
        with cache.batch():
            cache.touch('anything')

    assert len(cache) == 0


def test_batch_crash_leaves_cache_unchanged(cache):
    cache['stable'] = 'committed'
    stable_len = len(cache)
    before = len(value_files(cache.directory))

    child = os.path.join(cache.directory, '..', 'crash_child.py')
    with open(child, 'w', encoding='utf-8') as writer:
        writer.write(CRASH_CHILD)

    result = subprocess.run(
        [sys.executable, child, cache.directory, os.getcwd()],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 9, 'child did not die inside the batch'

    reopened = Cache(cache.directory)
    assert reopened.get('crashed') is None
    assert reopened.get('also-crashed') is None
    assert reopened['stable'] == 'committed'
    assert len(reopened) == stable_len
    assert len(value_files(cache.directory)) == before
    assert not unknown_file_warnings(reopened)
