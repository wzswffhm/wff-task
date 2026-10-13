"""Section table decoding and relative-virtual-address translation."""

import struct

from .errors import KIND_TRUNCATED, WImgError
from .headers import (
    SECTION_HEADER_SIZE,
    read_dos_header,
    read_file_header,
    read_optional_header,
)


def section_table_offset(optional_offset, size_of_optional_header):
    """Return where the section table starts for an optional header."""
    return optional_offset + size_of_optional_header


def decode_section(raw):
    """Turn one 40-byte section header into a dictionary."""
    virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
        "<IIII", raw, 8)
    return {
        "name": raw[0:8].rstrip(b"\0").decode("latin-1"),
        "virtual_address": virtual_address,
        "virtual_size": virtual_size,
        "raw_pointer": raw_pointer,
        "raw_size": raw_size,
        "characteristics": struct.unpack_from("<I", raw, 36)[0],
    }


def read_sections(data, offset, count):
    """Return the section table of an image."""
    if count < 0 or offset + count * SECTION_HEADER_SIZE > len(data):
        raise WImgError(KIND_TRUNCATED, "the section table is incomplete")
    sections = []
    for index in range(count):
        base = offset + index * SECTION_HEADER_SIZE
        sections.append(decode_section(data[base:base + SECTION_HEADER_SIZE]))
    return sections


def load_layout(data):
    """Parse the header chain of ``data`` without judging its contents."""
    nt_offset = read_dos_header(data)
    file_header = read_file_header(data, nt_offset)
    optional = read_optional_header(
        data,
        file_header["optional_offset"],
        file_header["size_of_optional_header"],
    )
    sections = read_sections(
        data,
        section_table_offset(file_header["optional_offset"],
                             file_header["size_of_optional_header"]),
        file_header["number_of_sections"],
    )
    return file_header, optional, sections


def rva_to_offset(data, rva):
    """Translate a relative virtual address into a file offset.

    Returns ``None`` when the address has no file backing.
    """
    if rva < 0:
        return None
    _file_header, optional, sections = load_layout(data)
    if rva < optional["size_of_headers"]:
        return rva
    for section in sections:
        start = section["virtual_address"]
        if start <= rva < start + section["virtual_size"]:
            delta = rva - start
            if delta >= section["raw_size"]:
                return None
            return section["raw_pointer"] + delta
    return None
