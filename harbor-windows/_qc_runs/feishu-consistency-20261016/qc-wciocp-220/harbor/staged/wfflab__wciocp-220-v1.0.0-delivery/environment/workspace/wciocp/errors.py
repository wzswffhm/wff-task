"""Error taxonomy for :mod:`wciocp`."""


class WCIOCPError(Exception):
    """Raised when a completion-pool call cannot be carried out.

    ``kind`` classifies the failure so that callers can react differently:

    ``"unsupported"``
        The object, the argument or the runtime cannot support the requested
        operation.  Retrying the same call will never help.
    ``"badarg"``
        The caller passed an unusable argument.
    ``"os"``
        The operating system rejected the call, and the rejection does not fall
        into any of the classes above.
    ``"timeout"``
        Nothing was handed back to the caller before its deadline passed.
    ``"closed"``
        The pool has been closed and no longer serves the call.
    """

    KINDS = ("unsupported", "badarg", "os", "timeout", "closed")

    def __init__(self, message, kind="os", handle=None):
        super().__init__(message)
        self.kind = kind
        self.handle = handle

    def __str__(self):
        base = super().__str__()
        if self.handle is None:
            return base
        return "%s (handle %r)" % (base, self.handle)
