"""Pre-allocation of sink files."""

import os

from .errors import WSParseError

#: Size of one reservation block.  The tail of a sink is written out in whole
#: blocks so that the writer never has to grow the file while it streams.
_BLOCK = 1 << 20


def _check_size(size):
    if isinstance(size, bool) or not isinstance(size, int):
        raise WSParseError("size must be an integer, got %r" % (size,), kind="badarg")
    if size < 0:
        raise WSParseError("size must not be negative, got %r" % (size,), kind="badarg")


def _open_for_update(path):
    try:
        return open(path, "r+b")
    except FileNotFoundError:
        try:
            return open(path, "w+b")
        except OSError as exc:
            raise WSParseError(str(exc), kind="os", path=path) from exc
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc


def preallocate(path, size):
    """Grow ``path`` to ``size`` bytes and reserve the space for it.

    The sink is created when it does not exist yet.  Existing content is
    preserved; the file is only ever extended, never shrunk.  The call is
    idempotent -- calling it again with the same ``size`` leaves the file
    untouched.

    Returns the resulting file length in bytes.
    """
    _check_size(size)
    path = os.fspath(path)
    handle = _open_for_update(path)
    try:
        handle.seek(0, os.SEEK_END)
        remaining = size - handle.tell()
        if remaining > 0:
            # Reserve the tail by writing it out.  The collector's writer fills
            # these bytes in later, so the intermediate content does not matter.
            block = b"\x00" * _BLOCK
            while remaining > 0:
                take = _BLOCK if remaining > _BLOCK else remaining
                handle.write(block[:take])
                remaining -= take
        handle.flush()
        os.fsync(handle.fileno())
        return handle.tell()
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    finally:
        handle.close()
