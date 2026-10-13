"""Streaming access to the section table of an image."""

from .headers import (
    SECTION_HEADER_SIZE,
    read_dos_header,
    read_file_header,
)
from .layout import decode_section, read_sections, section_table_offset


def iter_sections(fileobj):
    """Yield the section table entries of the image behind ``fileobj``."""
    data = fileobj.read()
    nt_offset = read_dos_header(data)
    file_header = read_file_header(data, nt_offset)
    sections = read_sections(
        data,
        section_table_offset(file_header["optional_offset"]),
        file_header["number_of_sections"],
    )
    for section in sections:
        yield section
