"""Error taxonomy for the portable executable inspector.

Every failure raised by this package is a :class:`WImgError` carrying a
machine-readable ``kind``.  The kinds are part of the public contract: callers
branch on them rather than parsing messages, so the spelling of each kind is
fixed.
"""

KIND_DOS = "dos"
KIND_SIGNATURE = "signature"
KIND_OPTIONAL = "optional"
KIND_TRUNCATED = "truncated"
KIND_STRUCTURE = "structure"
KIND_CHECKSUM = "checksum"

KINDS = (
    KIND_DOS,
    KIND_SIGNATURE,
    KIND_OPTIONAL,
    KIND_TRUNCATED,
    KIND_STRUCTURE,
    KIND_CHECKSUM,
)


class WImgError(Exception):
    """Raised when an image cannot be inspected or does not verify."""

    def __init__(self, kind, message=""):
        if kind not in KINDS:
            raise ValueError("unknown image error kind: %r" % (kind,))
        super(WImgError, self).__init__(message or kind)
        self.kind = kind
        self.message = message

    def __str__(self):
        if self.message:
            return "%s: %s" % (self.kind, self.message)
        return self.kind
