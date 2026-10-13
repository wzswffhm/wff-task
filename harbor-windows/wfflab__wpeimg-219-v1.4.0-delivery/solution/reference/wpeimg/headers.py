"""Fixed-layout decoding of the DOS, NT and optional headers."""

import struct

from .errors import (
    KIND_DOS,
    KIND_OPTIONAL,
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

# Everything up to and including the data directory array.
OPTIONAL_FIXED_PE32 = 96
OPTIONAL_FIXED_PE32_PLUS = 112

# Where NumberOfRvaAndSizes lives, per optional header layout.
NUMBER_OF_RVA_AND_SIZES_OFFSET_PE32 = 92
NUMBER_OF_RVA_AND_SIZES_OFFSET_PE32_PLUS = 108

DIRECTORY_ENTRY_SIZE = 8
CERTIFICATE_TABLE_INDEX = 4

# The canonical directory order of the PE format.  The array is positional, so
# an image that declares fewer entries than this leaves the tail unnamed but
# still present as zeros.
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
    if nt_offset < 0 or nt_offset + 4 + FILE_HEADER_SIZE > len(data):
        raise WImgError(KIND_TRUNCATED, "the NT headers are incomplete")
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


def read_optional_header(data, offset, size_of_optional_header):
    """Return the optional header fields this tool reports on."""
    if offset + 2 > len(data):
        raise WImgError(KIND_TRUNCATED, "the optional header is incomplete")
    magic = struct.unpack_from("<H", data, offset)[0]
    if magic == PE32_PLUS_MAGIC:
        is_plus = True
    elif magic == PE32_MAGIC:
        is_plus = False
    else:
        raise WImgError(
            KIND_OPTIONAL,
            "the optional header magic 0x%04X is neither 0x10B nor 0x20B" % magic)
    fixed = OPTIONAL_FIXED_PE32_PLUS if is_plus else OPTIONAL_FIXED_PE32
    if offset + fixed > len(data):
        raise WImgError(KIND_TRUNCATED, "the optional header is incomplete")
    if size_of_optional_header < fixed:
        raise WImgError(
            KIND_OPTIONAL,
            "SizeOfOptionalHeader %d cannot hold the optional header"
            % size_of_optional_header)
    entry_point = struct.unpack_from("<I", data, offset + 16)[0]
    if is_plus:
        image_base = struct.unpack_from("<Q", data, offset + 24)[0]
    else:
        image_base = struct.unpack_from("<I", data, offset + 28)[0]
    section_alignment, file_alignment = struct.unpack_from("<II", data, offset + 32)
    size_of_image, size_of_headers = struct.unpack_from("<II", data, offset + 56)
    checksum, subsystem = struct.unpack_from("<IH", data, offset + 64)

    # The directory array is positional and its length is declared separately
    # from SizeOfOptionalHeader.  PE32 and PE32+ place the count field at
    # different offsets (8 bytes apart), and an image may declare fewer entries
    # than the canonical sixteen; the remaining slots are still present (zero).
    count_offset = (NUMBER_OF_RVA_AND_SIZES_OFFSET_PE32_PLUS if is_plus
                    else NUMBER_OF_RVA_AND_SIZES_OFFSET_PE32)
    declared = struct.unpack_from("<I", data, offset + count_offset)[0]
    directories_offset = offset + (OPTIONAL_FIXED_PE32_PLUS if is_plus
                                   else OPTIONAL_FIXED_PE32)
    entries = []
    for index, name in enumerate(DIRECTORY_NAMES):
        if index >= declared:
            virtual_address, size = 0, 0
        else:
            entry_offset = directories_offset + index * DIRECTORY_ENTRY_SIZE
            if entry_offset + DIRECTORY_ENTRY_SIZE > offset + size_of_optional_header:
                # The declared count runs past the optional header the image
                # actually carries: the extra slots do not exist.
                virtual_address, size = 0, 0
            elif entry_offset + DIRECTORY_ENTRY_SIZE > len(data):
                virtual_address, size = 0, 0
            else:
                virtual_address, size = struct.unpack_from("<II", data, entry_offset)
        entries.append({
            "name": name,
            "virtual_address": virtual_address,
            "size": size,
        })

    return {
        "magic": magic,
        "is_pe32_plus": is_plus,
        "entry_point_rva": entry_point,
        "image_base": image_base,
        "section_alignment": section_alignment,
        "file_alignment": file_alignment,
        "size_of_image": size_of_image,
        "size_of_headers": size_of_headers,
        "checksum": checksum,
        "subsystem": subsystem,
        "number_of_rva_and_sizes": declared,
        "data_directories": entries,
    }
