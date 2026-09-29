"""Verify crash recovery: an unfinished batch leaves nothing behind."""
import os
import subprocess
import sys
import tempfile
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'baseline'))

from diskcache import Cache  # noqa: E402

CHILD = os.path.join(HERE, 'crash_child.py')


def count_files(directory):
    return len([name for name in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, name))])


def main():
    tmp = tempfile.mkdtemp(prefix='obm-crash-')
    directory = os.path.join(tmp, 'cache')

    before = Cache(directory)
    before['stable'] = 'committed'
    before_len = len(before)
    del before

    result = subprocess.run([sys.executable, CHILD, directory],
                            capture_output=True, text=True)
    print('child returncode:', result.returncode)
    print('child stderr:', result.stderr.strip()[:60])
    print('files right after crash:', count_files(directory))

    reopened = Cache(directory)
    print('after reopen: crashed=%r also=%r stable=%r len=%r'
          % (reopened.get('crashed'), reopened.get('also'),
             reopened.get('stable'), len(reopened)))
    print('expected len:', before_len + 1)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        reopened.check()
        messages = [str(item.message)[:60] for item in caught]
    print('check warnings:', messages)

    reopened.check(fix=True)
    print('files after check(fix=True):', count_files(directory))
    print('CRASHTEST DONE')


if __name__ == '__main__':
    main()
