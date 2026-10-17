"""Error taxonomy for :mod:`wsparse`."""


class WSParseError(Exception):
    """Raised when a space-management operation cannot be carried out.

    ``kind`` classifies the failure so that callers can react differently:

    ``"unsupported"``
        The file system, the volume, or the object being addressed does not
        support the requested sparse-file operation.  Retrying on the same
        object will never help.
    ``"os"``
        The operating system rejected the operation: an I/O error, a sharing
        violation, a missing path, and so on.
    ``"badarg"``
        The caller passed an unusable argument.
    """

    KINDS = ("unsupported", "os", "badarg")

    def __init__(self, message, kind="os", path=None):
        super().__init__(message)
        self.kind = kind
        self.path = path

    def __str__(self):
        base = super().__str__()
        if self.path is None:
            return base
        return "%s: %s" % (self.path, base)
