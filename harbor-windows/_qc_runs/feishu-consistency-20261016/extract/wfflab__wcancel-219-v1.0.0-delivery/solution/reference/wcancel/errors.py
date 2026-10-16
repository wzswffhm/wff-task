"""Error taxonomy for :mod:`wcancel`."""


class WCancelError(Exception):
    """Raised when an overlapped-read operation cannot be carried out.

    ``kind`` classifies the failure so that callers can react differently:

    ``"unsupported"``
        The object cannot carry overlapped I/O at all -- it was opened without
        ``FILE_FLAG_OVERLAPPED``, so a pending request on it could never be
        cancelled precisely.  Retrying the same call will never help.
    ``"badarg"``
        The caller passed an unusable argument (a null or invalid handle, a
        size that is not a positive count, a negative offset).
    ``"timeout"``
        ``wait`` reached its deadline while the request was still outstanding.
        The request is untouched and may be waited on again.
    ``"os"``
        The operating system rejected the call.  ``error`` carries the Win32
        code when there is one.
    """

    KINDS = ("unsupported", "badarg", "os", "timeout")

    def __init__(self, message, kind="os", handle=None, error=None):
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
