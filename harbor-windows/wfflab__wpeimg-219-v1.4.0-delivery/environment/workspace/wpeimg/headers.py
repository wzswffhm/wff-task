"""Fixed-layout decoding of the DOS, NT and optional headers."""

import struct

from .errors import (
    KIND_DOS,
    KIND_SIGNATURE,
    KIND_TRUNCATED,
    WImgError,
)

DOS_HEADER_SIZE = 0x40
DOS_MAGIC = b"MZ"
NT_SIGNATURE = b"PE\0\0"
PE32_MAGIC = 0x10B
PE32_PLUS_MAGIC = 0x20B
FILE_HEADER_SIZE = 20
SECTION_HEADER_SIZE = 40
CHECKSUM_OFFSET = 64

DIRECTORY_ENTRY_SIZE = 8
CERTIFICATE_TABLE_INDEX = 4
DIRECTORY_NAMES = (
    "export",
    "import",
    "resource",
    "exception",
    "certificate",
    "relocation",
    "debug",
    "architecture",
    "global_ptr",
    "tls",
    "load_config",
    "bound_import",
    "iat",
    "delay_import",
    "clr_runtime",
    "reserved",
)


def read_dos_header(data):
    """Return the offset of the NT headers recorded at 0x3C."""
    if len(data) < DOS_HEADER_SIZE:
        raise WImgError(KIND_TRUNCATED, "the DOS header is incomplete")
    if data[:2] != DOS_MAGIC:
        raise WImgError(KIND_DOS, "the image does not begin with MZ")
    return struct.unpack_from("<I", data, 0x3C)[0]


def read_file_header(data, nt_offset):
    """Return the COFF file header that follows the NT signature."""
    if data[nt_offset:nt_offset + 4] != NT_SIGNATURE:
        raise WImgError(KIND_SIGNATURE, "the PE signature is missing")
    coff = nt_offset + 4
    machine, nsec, _stamp, _symtab, _nsym, size_opt, _chars = struct.unpack_from(
        "<HHIIIHH", data, coff)
    return {
        "machine": machine,
        "number_of_sections": nsec,
        "size_of_optional_header": size_opt,
        "optional_offset": coff + FILE_HEADER_SIZE,
    }


def read_optional_header(data, offset):
    """Return the optional header fields this tool reports on."""
    magic = struct.unpack_from("<H", data, offset)[0]
    entry_point = struct.unpack_from("<I", data, offset + 16)[0]
    image_base = struct.unpack_from("<Q", data, offset + 24)[0]
    section_alignment, file_alignment = struct.unpack_from("<II", data, offset + 32)
    size_of_image, size_of_headers = struct.unpack_from("<II", data, offset + 56)
    checksum, subsystem = struct.unpack_from("<IH", data, offset + 64)

    # TODO: the directory array is the one part of the optional header that is
    # not at a fixed offset -- it depends on the layout (PE32/PE32+) and on how
    # many entries the image declares.  This placeholder reads it as if every
    # image were PE32+ and as if every image declared all sixteen entries.
    directories = []
    for index, name in enumerate(DIRECTORY_NAMES):
        entry_offset = offset + 112 + index * DIRECTORY_ENTRY_SIZE
        virtual_address, size = struct.unpack_from("<II", data, entry_offset)
        directories.append({
            "name": name,
            "virtual_address": virtual_address,
            "size": size,
        })

    return {
        "magic": magic,
        "entry_point_rva": entry_point,
        "image_base": image_base,
        "section_alignment": section_alignment,
        "file_alignment": file_alignment,
        "size_of_image": size_of_image,
        "size_of_headers": size_of_headers,
        "checksum": checksum,
        "subsystem": subsystem,
        "data_directories": directories,
    }
