"""Child helper: write inside a batch and die without committing."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'baseline'))

from diskcache import Cache  # noqa: E402

directory = sys.argv[1]
cache = Cache(directory)
with cache.batch():
    cache['crashed'] = 'payload'
    cache['also'] = 'second'
    sys.stderr.write('child staged rows, dying inside the batch now\n')
    sys.stderr.flush()
    os._exit(9)
