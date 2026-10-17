"""wvas - a small virtual address space auditor for Windows diagnostics."""

from .errors import WVasError
from .vas import (
    file_backed_regions,
    modules,
    protection_name,
    regions,
    type_name,
)

__all__ = [
    "WVasError",
    "file_backed_regions",
    "modules",
    "protection_name",
    "regions",
    "type_name",
]

__version__ = "1.0.0"
