# Field notes: the optional header

Scratch notes kept while `wpeimg` was first written. They describe the 64-bit
layout this tool was developed against; they are not a specification.

## Where things sit

The file starts with a 64-byte DOS header. Only two bytes of it matter here:
`MZ` at offset 0, and the little-endian double word at `0x3C` giving the offset
of the NT headers. The NT headers are the four-byte signature `PE\0\0` followed
by the 20-byte COFF file header.

The interesting COFF fields are `Machine` and `NumberOfSections`. The optional
header follows immediately.

## Optional header

For the images this tool was written against the optional header is 224 bytes,
so the section table starts 224 bytes past the beginning of the optional header:

```
optional_header_offset + 224  ->  first SECTION_HEADER (40 bytes each)
```

Two layouts exist. `Magic` is `0x10B` for 32-bit images and `0x20B` for 64-bit
images. The offsets that differ:

| Field | 0x10B | 0x20B |
| --- | --- | --- |
| `ImageBase` | `+28`, 4 bytes | `+24`, 8 bytes |
| `SizeOfStackReserve` | `+72`, 4 bytes | `+72`, 8 bytes |

Everything this tool reads sits before those differences:

| Field | Offset | Width |
| --- | --- | --- |
| `AddressOfEntryPoint` | `+16` | 4 |
| `SectionAlignment` | `+32` | 4 |
| `FileAlignment` | `+36` | 4 |
| `SizeOfImage` | `+56` | 4 |
| `SizeOfHeaders` | `+60` | 4 |
| `CheckSum` | `+64` | 4 |
| `Subsystem` | `+68` | 2 |

## CheckSum

`CheckSum` is the value the loader compares against when it is non-zero. A
module whose `CheckSum` field is zero is treated as unchecked.

The value is not a CRC. It is a running sum of the file, and Windows exposes it
through the image helper library rather than documenting the fold in the SDK.

## Section table

Each entry is 40 bytes: an eight-byte name padded with NULs, then
`VirtualSize`, `VirtualAddress`, `SizeOfRawData` and `PointerToRawData` as
little-endian double words, and `Characteristics` at `+36`.

`VirtualAddress` is relative to `ImageBase`. The image header itself occupies
the first `SizeOfHeaders` bytes of the file and is mapped at the bottom of the
address space, so addresses below `SizeOfHeaders` are not backed by any section.
