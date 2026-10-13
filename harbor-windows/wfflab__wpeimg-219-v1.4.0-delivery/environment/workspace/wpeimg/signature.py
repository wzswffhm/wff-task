"""Authenticode signature decoding (work in progress).

The certificate table points at a ``WIN_CERTIFICATE`` record whose body is a
PKCS#7 ``SignedData`` DER blob.  This module is supposed to describe what that
blob actually contains.
"""

WIN_CERT_TYPE_PKCS_SIGNED_DATA = 0x0002


def signature_info(head):
    """Describe the certificate table of *head*.

    TODO: this only reports the ``WIN_CERTIFICATE`` header fields.  It never
    looks inside the DER blob, so the PKCS#7 part (the content type, the digest
    algorithms, how many certificates the blob carries and how many signers it
    has) always comes back empty, and a record whose declared length does not
    fit the file is reported as if it were fine.
    """
    info = {
        "present": False,
        "offset": 0,
        "size": 0,
        "declared_length": 0,
        "revision": 0,
        "certificate_type": 0,
        "content_type": None,
        "digest_algorithms": [],
        "certificate_count": 0,
        "signer_count": 0,
    }
    if not head:
        return info
    try:
        from .headers import CERTIFICATE_TABLE_INDEX, read_dos_header, read_file_header
        from .headers import read_optional_header
        nt = read_dos_header(head)
        file_header = read_file_header(head, nt)
        optional = read_optional_header(
            head, file_header["optional_offset"], file_header["size_of_optional_header"])
    except Exception:  # noqa: BLE001
        return info
    directories = optional.get("data_directories") or []
    if CERTIFICATE_TABLE_INDEX >= len(directories):
        return info
    entry = directories[CERTIFICATE_TABLE_INDEX]
    offset, size = entry.get("virtual_address") or 0, entry.get("size") or 0
    if not offset or not size or offset + size > len(head):
        return info
    info["present"] = True
    info["offset"] = offset
    info["size"] = size
    info["certificate_type"] = WIN_CERT_TYPE_PKCS_SIGNED_DATA
    return info
