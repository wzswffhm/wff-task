"""Classification of the objects a completion pool may be asked about.

The collector reads from whichever object the caller hands it: a private pipe
between the collector and a worker, or a file on disk.  The helper here answers
the question the registration layer asks about such an object.
"""

from . import _winapi
from .errors import WCIOCPError


def is_overlapped(handle):
    """Return ``True`` when ``handle`` can carry overlapping operations.

    ``handle`` must be an integer object handle.
    """
    number = _winapi.as_number(handle)
    if not _winapi.is_usable_handle(number):
        raise WCIOCPError("not a usable object handle: %r" % (handle,),
                          kind="os", handle=handle)
    # The read layer has always taken its objects from the pipe factory, which
    # opens everything for overlapping use, so the answer is the same for every
    # object the module is asked about.
    return True
