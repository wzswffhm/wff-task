"""Error taxonomy for :mod:`wciocp`.

Every failure the completion layer can report belongs to one of five kinds, so a
caller can react without parsing messages:

``"unsupported"``
    The object cannot carry overlapping (asynchronous) operations, because it
    was not opened with ``FILE_FLAG_OVERLAPPED``.  Retrying will never help.
``"badarg"``
    The caller passed an unusable argument: a non-integer handle, a null or
    stale handle, a size that is not a positive count, a negative offset, a
    request that does not belong to this pool.
``"os"``
    A Win32/NT call failed and the failure falls into none of the classes above.
    ``error`` carries the Win32 code when there is one.
``"timeout"``
    ``take()`` reached its deadline before a completion packet arrived.  The
    packets already sitting in the port are *not* affected.
``"closed"``
    The pool was closed.  ``take()`` and ``submit()`` refuse to run afterwards.
"""

__all__ = ["WCIOCPError", "KINDS"]


#: The complete vocabulary of ``WCIOCPError.kind``.
KINDS = ("unsupported", "badarg", "os", "timeout", "closed")


class WCIOCPError(Exception):
    """Raised when a completion-port operation cannot be carried out.

    ``kind`` is always one of :data:`KINDS`.  ``handle`` carries the object the
    failure is about and ``error`` the Win32 code behind it; both show up in
    ``str()`` when they are set.
    """

    KINDS = KINDS

    def __init__(self, message, kind="os", handle=None, error=None):
        if kind not in KINDS:
            raise ValueError("unknown WCIOCPError kind: %r" % (kind,))
        super().__init__(message)
        self.kind = kind
        self.handle = handle
        self.error = error

    def __str__(self):
        base = super().__str__()
        details = []
        if self.handle is not None:
            details.append("handle %r" % (self.handle,))
        if self.error is not None:
            details.append("Win32 error %r" % (self.error,))
        if not details:
            return base
        return "%s (%s)" % (base, ", ".join(details))

    def __repr__(self):
        return "WCIOCPError(%r, kind=%r)" % (super().__str__(), self.kind)
