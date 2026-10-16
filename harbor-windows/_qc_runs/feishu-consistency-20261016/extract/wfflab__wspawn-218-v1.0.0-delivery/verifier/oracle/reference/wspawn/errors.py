"""Error taxonomy for :mod:`wspawn`."""


class WSpawnError(Exception):
    """Raised when a handle-handover operation cannot be carried out.

    ``kind`` classifies the failure so that callers can react differently:

    ``"unsupported"``
        The object, the argument or the runtime cannot support the requested
        operation.  Retrying the same call will never help.
    ``"os"``
        The operating system rejected the call.
    ``"badarg"``
        The caller passed an unusable argument.
    """

    KINDS = ("unsupported", "os", "badarg")

    def __init__(self, message, kind="os", handle=None):
        super().__init__(message)
        self.kind = kind
        self.handle = handle

    def __str__(self):
        base = super().__str__()
        if self.handle is None:
            return base
        return "%s (handle %r)" % (base, self.handle)
