"""Streaming access to the section table of an image."""

import struct

from .errors import (
    KIND_DOS,
    KIND_SIGNATURE,
    KIND_TRUNCATED,
    WImgError,
)
from .headers import (
    DOS_HEADER_SIZE,
    DOS_MAGIC,
    FILE_HEADER_SIZE,
    NT_SIGNATURE,
    SECTION_HEADER_SIZE,
)
from .layout import decode_section


def _read_exactly(fileobj, offset, size):
    fileobj.seek(offset)
    return fileobj.read(size)


def iter_sections(fileobj):
    """Yield the section table entries of the image behind ``fileobj``.

    The stream is read in fixed-size pieces and only as far as the caller
    actually consumes it.
    """
    dos = _read_exactly(fileobj, 0, DOS_HEADER_SIZE)
    if len(dos) < DOS_HEADER_SIZE:
        raise WImgError(KIND_TRUNCATED, "the DOS header is incomplete")
    if dos[:2] != DOS_MAGIC:
        raise WImgError(KIND_DOS, "the image does not begin with MZ")
    nt_offset = struct.unpack_from("<I", dos, 0x3C)[0]
    nt_headers = _read_exactly(fileobj, nt_offset, 4 + FILE_HEADER_SIZE)
    if len(nt_headers) < 4 + FILE_HEADER_SIZE:
        raise WImgError(KIND_TRUNCATED, "the NT headers are incomplete")
    if nt_headers[:4] != NT_SIGNATURE:
        raise WImgError(KIND_SIGNATURE, "the PE signature is missing")
    _machine, count, _stamp, _symtab, _nsym, size_opt, _chars = struct.unpack_from(
        "<HHIIIHH", nt_headers, 4)
    table = nt_offset + 4 + FILE_HEADER_SIZE + size_opt
    for index in range(count):
        base = table + index * SECTION_HEADER_SIZE
        raw = _read_exactly(fileobj, base, SECTION_HEADER_SIZE)
        if len(raw) < SECTION_HEADER_SIZE:
            raise WImgError(KIND_TRUNCATED, "the section table is incomplete")
        yield decode_section(raw)
