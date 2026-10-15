"""Error taxonomy for :mod:`wtoken`."""


class WTokenError(Exception):
    """Raised when a token operation cannot be carried out.

    ``kind`` classifies the failure so that callers can react differently:

    ``"unsupported"``
        The runtime or the requested operation cannot be supported here.
        Retrying the same call will never help.
    ``"os"``
        The operating system rejected the call.
    ``"badarg"``
        The caller passed an unusable argument.
    """

    KINDS = ("unsupported", "os", "badarg")

    def __init__(self, message, kind="os", privilege=None):
        super().__init__(message)
        self.kind = kind
        self.privilege = privilege

    def __str__(self):
        base = super().__str__()
        if self.privilege is None:
            return base
        return "%s (privilege %r)" % (base, self.privilege)
