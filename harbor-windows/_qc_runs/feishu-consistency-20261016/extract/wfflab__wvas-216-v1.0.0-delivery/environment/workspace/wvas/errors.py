"""Error taxonomy for the wvas address-space auditor.

Every failure surfaced by the public API is a :class:`WVasError`. The ``kind``
attribute carries the machine readable classification the diagnostic tooling
switches on, so callers never have to parse an English message.
"""

KINDS = (
    "badarg",          # the caller passed something the API cannot use
    "no-such-process",  # the pid does not name a running process
    "access-denied",   # the process exists but cannot be opened for reading
    "unsupported",     # the platform cannot answer this question at all
    "query-failed",    # the Win32 call itself failed for another reason
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
