"""High-level entry points: describe an image, or ask whether it verifies."""

from .checksum import compute_checksum
from .errors import KIND_CHECKSUM, WImgError
from .layout import load_layout


def inspect(data):
    """Return the structural facts of one image.

    Raises :class:`WImgError` when the bytes are not an image this tool
    accepts.
    """
    _file_header, optional, sections = load_layout(data)
    recorded = optional["checksum"]
    if recorded and recorded != compute_checksum(data):
        raise WImgError(KIND_CHECKSUM, "the recorded checksum does not match the file")
    return {
        "machine": _file_header["machine"],
        "is_pe32_plus": True,
        "number_of_sections": _file_header["number_of_sections"],
        "entry_point_rva": optional["entry_point_rva"],
        "image_base": optional["image_base"],
        "section_alignment": optional["section_alignment"],
        "file_alignment": optional["file_alignment"],
        "size_of_image": optional["size_of_image"],
        "size_of_headers": optional["size_of_headers"],
        "checksum": recorded,
        "sections": sections,
    }


def verify(data):
    """Return whether ``data`` is an image this tool accepts."""
    try:
        inspect(data)
    except Exception:
        return False
    return True
