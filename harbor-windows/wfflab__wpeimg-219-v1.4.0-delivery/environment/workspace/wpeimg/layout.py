"""Section table decoding and relative-virtual-address translation."""

import struct

from .headers import (
    SECTION_HEADER_SIZE,
    read_dos_header,
    read_file_header,
    read_optional_header,
)

OPTIONAL_HEADER_BYTES = 224


def section_table_offset(optional_offset):
    """Return where the section table starts for an optional header."""
    return optional_offset + OPTIONAL_HEADER_BYTES


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
    sections = []
    for index in range(count):
        base = offset + index * SECTION_HEADER_SIZE
        sections.append(decode_section(data[base:base + SECTION_HEADER_SIZE]))
    return sections


def load_layout(data):
    """Parse the header chain of ``data`` without judging its contents."""
    nt_offset = read_dos_header(data)
    file_header = read_file_header(data, nt_offset)
    optional = read_optional_header(data, file_header["optional_offset"])
    sections = read_sections(
        data,
        section_table_offset(file_header["optional_offset"]),
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
    virtual = rva - optional["image_base"]
    for section in sections:
        start = section["virtual_address"]
        if start <= virtual < start + section["virtual_size"]:
            return section["raw_pointer"] + (virtual - start)
    return None
