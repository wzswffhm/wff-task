"""Local sanity check for the reference batch implementation."""
import os
import shutil
import sys
import tempfile
import time
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'baseline'))

from diskcache import Cache  # noqa: E402

TMP = tempfile.mkdtemp(prefix='obm-selftest-')


def fresh(name):
    return Cache(os.path.join(TMP, name))


def main():
    c = fresh('commit')
    with c.batch():
        c['a'] = 1
        c['b'] = 2
        assert c['a'] == 1, 'read-your-writes failed'
        assert len(c) == 2, 'len inside batch wrong: %r' % len(c)
    print('commit ok:', c['a'], c['b'], len(c))

    c2 = fresh('rollback')
    c2['keep'] = 'yes'
    try:
        with c2.batch():
            c2['x'] = 1
            c2.delete('keep')
            assert 'keep' not in c2, 'delete not visible inside batch'
            raise ValueError('boom')
    except ValueError:
        pass
    print('rollback ok: keep=%r x=%r len=%r' % (c2.get('keep'), c2.get('x'), len(c2)))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        c2.check()
        print('check warnings:', [str(item.message)[:50] for item in caught])

    c3 = fresh('isolation')
    other = Cache(c3.directory)
    with c3.batch():
        c3['hidden'] = 'v'
        print('isolation: self=%r other=%r other_len=%r'
              % (c3['hidden'], other.get('hidden'), len(other)))
    print('after commit: other=%r other_len=%r' % (other.get('hidden'), len(other)))

    c4 = fresh('overwrite')
    c4['k'] = 'old'
    with c4.batch():
        c4['k'] = 'new1'
        c4['k'] = 'new2'
        c4.delete('k')
        c4['k'] = 'final'
    print('overwrite ok: %r len=%r' % (c4['k'], len(c4)))

    c5 = fresh('expire')
    with c5.batch():
        c5.set('e', 'v', expire=0.2)
        print('inside batch (expire):', c5.get('e'))
    print('right after commit:', c5.get('e'))
    time.sleep(0.4)
    print('after expiry:', c5.get('e'))

    c6 = fresh('nested')
    try:
        with c6.batch():
            with c6.batch():
                pass
    except RuntimeError as exc:
        print('nested rejected:', str(exc)[:60])

    c7 = fresh('volume')
    base_volume = c7.volume()
    with c7.batch():
        c7['big'] = 'x' * 5000
        staged_volume = c7.volume()
    print('volume base=%d staged=%d committed=%d'
          % (base_volume, staged_volume, c7.volume()))

    shutil.rmtree(TMP, ignore_errors=True)
    print('SELFTEST DONE')


if __name__ == '__main__':
    main()
