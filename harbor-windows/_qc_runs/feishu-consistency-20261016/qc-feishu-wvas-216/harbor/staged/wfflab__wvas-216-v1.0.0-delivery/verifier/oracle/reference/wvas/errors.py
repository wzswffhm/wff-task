"""Error taxonomy for the wvas address-space auditor."""

KINDS = (
    "badarg",
    "no-such-process",
    "access-denied",
    "unsupported",
    "query-failed",
)


class WVasError(Exception):
    """A classified failure raised by :mod:`wvas`."""

    def __init__(self, message, kind="query-failed", pid=None):
        super().__init__(message)
        if kind not in KINDS:
            raise ValueError("unknown kind: %r" % (kind,))
        self.kind = kind
        self.pid = pid

    def __str__(self):
        if self.pid is None:
            return super().__str__()
        return "%s (pid=%s)" % (super().__str__(), self.pid)
