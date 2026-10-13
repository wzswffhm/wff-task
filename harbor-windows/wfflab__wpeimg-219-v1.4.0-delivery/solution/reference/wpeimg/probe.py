"""High-level entry points: describe an image, or ask whether it verifies."""

from .checksum import compute_checksum
from .errors import KIND_CHECKSUM, KIND_STRUCTURE, WImgError
from .headers import CERTIFICATE_TABLE_INDEX
from .layout import load_layout

SECTION_HEADER_SIZE = 40


def _has_authenticode_signature(data, optional):
    """Return whether the image carries a real Authenticode blob.

    The certificate table is the only directory whose first field is a *file
    offset* rather than a virtual address, and Windows treats a directory as
    present only when both fields are non-zero **and** the file really backs
    it.  An image that merely records a non-zero certificate entry it cannot
    back has no signature to verify.
    """
    directories = optional.get("data_directories") or []
    if CERTIFICATE_TABLE_INDEX >= len(directories):
        return False
    entry = directories[CERTIFICATE_TABLE_INDEX]
    if not entry.get("virtual_address") or not entry.get("size"):
        return False
    offset = entry["virtual_address"]
    if offset < 0 or offset + entry["size"] > len(data):
        return False
    return True


def _align_up(value, alignment):
    if alignment <= 0:
        return value
    return ((value + alignment - 1) // alignment) * alignment


def _check_structure(data, file_header, optional, sections):
    """Reject an image whose own description contradicts itself."""
    total = len(data)
    section_alignment = optional["section_alignment"]
    file_alignment = optional["file_alignment"]
    size_of_headers = optional["size_of_headers"]

    for index, section in enumerate(sections):
        name = section["name"] or "#%d" % index
        if section["raw_pointer"] + section["raw_size"] > total:
            raise WImgError(
                KIND_STRUCTURE,
                "section %s claims file bytes past the end of the image" % name)
        if section["raw_size"] and section["raw_pointer"] < size_of_headers:
            raise WImgError(
                KIND_STRUCTURE, "section %s starts inside the image headers" % name)
        if section_alignment and section["virtual_address"] % section_alignment:
            raise WImgError(
                KIND_STRUCTURE,
                "section %s is not aligned to SectionAlignment" % name)
        if file_alignment and section["raw_pointer"] % file_alignment:
            raise WImgError(
                KIND_STRUCTURE,
                "section %s is not aligned to FileAlignment" % name)

    for left in range(len(sections)):
        for right in range(left + 1, len(sections)):
            first = sections[left]
            second = sections[right]
            if (first["raw_size"] and second["raw_size"]
                    and first["raw_pointer"] < second["raw_pointer"] + second["raw_size"]
                    and second["raw_pointer"] < first["raw_pointer"] + first["raw_size"]):
                raise WImgError(
                    KIND_STRUCTURE,
                    "sections %s and %s overlap in the file"
                    % (first["name"], second["name"]))
            if (first["virtual_size"] and second["virtual_size"]
                    and first["virtual_address"] < second["virtual_address"] + second["virtual_size"]
                    and second["virtual_address"] < first["virtual_address"] + first["virtual_size"]):
                raise WImgError(
                    KIND_STRUCTURE,
                    "sections %s and %s overlap in memory"
                    % (first["name"], second["name"]))

    highest = 0
    for section in sections:
        highest = max(highest, section["virtual_address"] + section["virtual_size"])
    required = _align_up(highest, section_alignment)
    if optional["size_of_image"] < required:
        raise WImgError(
            KIND_STRUCTURE,
            "SizeOfImage 0x%X does not cover the sections (0x%X)"
            % (optional["size_of_image"], required))

    if file_alignment and size_of_headers % file_alignment:
        raise WImgError(
            KIND_STRUCTURE, "SizeOfHeaders is not aligned to FileAlignment")

    headers_end = (file_header["optional_offset"]
                   + file_header["size_of_optional_header"]
                   + file_header["number_of_sections"] * SECTION_HEADER_SIZE)
    if size_of_headers < headers_end:
        raise WImgError(
            KIND_STRUCTURE, "SizeOfHeaders does not cover the section table")


def inspect(data):
    """Return the structural facts of one image.

    Raises :class:`WImgError` when the bytes are not an image this tool
    accepts.  Every structural complaint is raised before the checksum is
    consulted, so a self-consistent but impossible image never reports as a
    checksum problem.
    """
    raw = bytes(data)
    file_header, optional, sections = load_layout(raw)
    _check_structure(raw, file_header, optional, sections)
    recorded = optional["checksum"]
    if recorded and recorded != compute_checksum(raw):
        raise WImgError(KIND_CHECKSUM, "the recorded checksum does not match the file")
    return {
        "machine": file_header["machine"],
        "is_pe32_plus": optional["is_pe32_plus"],
        "number_of_sections": file_header["number_of_sections"],
        "entry_point_rva": optional["entry_point_rva"],
        "image_base": optional["image_base"],
        "section_alignment": optional["section_alignment"],
        "file_alignment": optional["file_alignment"],
        "size_of_image": optional["size_of_image"],
        "size_of_headers": optional["size_of_headers"],
        "checksum": recorded,
        "sections": sections,
        "data_directories": optional["data_directories"],
        "has_authenticode_signature": _has_authenticode_signature(raw, optional),
    }


def verify(data):
    """Return whether ``data`` is an image this tool accepts."""
    try:
        inspect(data)
    except Exception:
        return False
    return True
