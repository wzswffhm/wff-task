"""wpeimg - a small inspector for Windows portable executable images."""

from .checksum import ChecksumAccumulator, compute_checksum
from .errors import (
    KIND_CHECKSUM,
    KIND_DOS,
    KIND_OPTIONAL,
    KIND_SIGNATURE,
    KIND_STRUCTURE,
    KIND_TRUNCATED,
    KINDS,
    WImgError,
)
from .layout import rva_to_offset
from .probe import inspect, verify
from .stream import iter_sections

__all__ = [
    "ChecksumAccumulator",
    "KIND_CHECKSUM",
    "KIND_DOS",
    "KIND_OPTIONAL",
    "KIND_SIGNATURE",
    "KIND_STRUCTURE",
    "KIND_TRUNCATED",
    "KINDS",
    "WImgError",
    "compute_checksum",
    "inspect",
    "iter_sections",
    "rva_to_offset",
    "verify",
]

__version__ = "0.4.0"
