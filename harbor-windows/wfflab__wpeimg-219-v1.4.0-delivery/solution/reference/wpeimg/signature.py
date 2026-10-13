"""Authenticode signature decoding.

The certificate-table directory entry points at a ``WIN_CERTIFICATE`` record
whose body is a PKCS#7 ``SignedData`` DER blob.  Windows uses the blob to bind
the image to its publisher, so reporting what it actually contains means
walking the DER by hand: the standard library ships no ASN.1 decoder and the
contract forbids calling into the OS.
"""

import struct

from .errors import KIND_STRUCTURE, WImgError

WIN_CERT_HEADER_SIZE = 8
WIN_CERT_TYPE_PKCS_SIGNED_DATA = 0x0002
WIN_CERT_REVISION_2_0 = 0x0200
WIN_CERT_REVISION_1_0 = 0x0100

# Authenticode uses the SPC indirect-data OID as its contentType.
SPC_INDIRECT_DATA_OID = "1.2.840.113549.1.7.2"

OID_NAMES = {
    "1.3.14.3.2.26": "sha1",
    "2.16.840.1.101.3.4.2.1": "sha256",
    "2.16.840.1.101.3.4.2.2": "sha384",
    "2.16.840.1.101.3.4.2.3": "sha512",
    "1.2.840.113549.1.1.1": "rsa",
    "1.2.840.113549.1.1.11": "sha256WithRSA",
    "1.2.840.113549.1.1.5": "sha1WithRSA",
    "1.2.840.10045.2.1": "ec",
    "1.2.840.10045.4.3.2": "ecdsaWithSHA256",
}


def decode_oid(raw):
    """Decode the value bytes of an OBJECT IDENTIFIER into dotted notation."""
    if not raw:
        return ""
    first = raw[0]
    parts = [str(first // 40), str(first % 40)]
    value = 0
    for byte in raw[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            parts.append(str(value))
            value = 0
    return ".".join(parts)


def read_tlv(buf, offset):
    """Return (tag, content_start, content_end, next_offset) for one TLV."""
    if offset + 2 > len(buf):
        raise WImgError(KIND_STRUCTURE, "the signature structure is truncated")
    tag = buf[offset]
    length = buf[offset + 1]
    header = 2
    if length & 0x80:
        count = length & 0x7F
        if count == 0:
            raise WImgError(KIND_STRUCTURE, "indefinite ASN.1 lengths are not valid DER")
        if offset + 2 + count > len(buf):
            raise WImgError(KIND_STRUCTURE, "the signature structure is truncated")
        length = int.from_bytes(buf[offset + 2:offset + 2 + count], "big")
        header = 2 + count
    start = offset + header
    end = start + length
    if end > len(buf):
        raise WImgError(KIND_STRUCTURE, "the signature structure is truncated")
    return tag, start, end, end


def iter_children(buf, start, end):
    """Yield (tag, content_start, content_end) for a constructed value."""
    pos = start
    while pos < end:
        tag, cs, ce, nxt = read_tlv(buf, pos)
        yield tag, cs, ce
        if nxt <= pos:
            raise WImgError(KIND_STRUCTURE, "the signature structure does not advance")
        pos = nxt


def _first_oid(buf, start, end):
    for tag, cs, ce in iter_children(buf, start, end):
        if tag == 0x06:
            return decode_oid(buf[cs:ce])
    return ""


def _walk_signed_data(der):
    """Return the child TLVs of the SignedData SEQUENCE, or raise."""
    tag, outer_s, outer_e, _ = read_tlv(der, 0)
    if tag != 0x30:
        raise WImgError(KIND_STRUCTURE, "the signature does not start with a DER SEQUENCE")
    content_type = ""
    explicit = None
    for ctag, cs, ce in iter_children(der, outer_s, outer_e):
        if ctag == 0x06 and not content_type:
            content_type = decode_oid(der[cs:ce])
        elif ctag == 0xA0:
            explicit = (cs, ce)
    if explicit is None:
        raise WImgError(KIND_STRUCTURE, "the signature has no SignedData content")
    inner_tag, in_s, in_e, _ = read_tlv(der, explicit[0])
    if inner_tag != 0x30:
        raise WImgError(KIND_STRUCTURE, "SignedData is not a DER SEQUENCE")
    return content_type, list(iter_children(der, in_s, in_e))


def signature_info(head: bytes) -> dict:
    """Describe the certificate table of *head*.

    ``head`` is the whole image, or at least every byte the certificate entry
    claims.  The return value describes the *structure* of the blob and is
    empty (all ``None`` / 0) when the image carries no certificate table.
    """
    if not head:
        return _empty()
    # The caller passes the image; the certificate entry is re-read here so the
    # function is usable on its own.
    try:
        from .headers import CERTIFICATE_TABLE_INDEX, read_dos_header, read_file_header
        from .headers import read_optional_header
        nt = read_dos_header(head)
        file_header = read_file_header(head, nt)
        optional = read_optional_header(
            head, file_header["optional_offset"], file_header["size_of_optional_header"])
    except Exception:  # noqa: BLE001 - a headless image simply has no signature
        return _empty()
    directories = optional.get("data_directories") or []
    if CERTIFICATE_TABLE_INDEX >= len(directories):
        return _empty()
    entry = directories[CERTIFICATE_TABLE_INDEX]
    offset, size = entry.get("virtual_address") or 0, entry.get("size") or 0
    if not offset or not size or offset + size > len(head):
        return _empty()
    blob = bytes(head[offset:offset + size])
    if len(blob) < WIN_CERT_HEADER_SIZE:
        raise WImgError(KIND_STRUCTURE, "the certificate record is shorter than its header")
    declared, revision, cert_type = struct.unpack_from("<IHH", blob, 0)
    if declared < WIN_CERT_HEADER_SIZE or declared > len(blob):
        raise WImgError(
            KIND_STRUCTURE,
            "the certificate record declares %d bytes but only %d are present"
            % (declared, len(blob)))
    der = blob[WIN_CERT_HEADER_SIZE:declared]
    info = _empty()
    info.update({
        "present": True,
        "offset": offset,
        "size": size,
        "declared_length": declared,
        "revision": revision,
        "certificate_type": cert_type,
    })
    if cert_type != WIN_CERT_TYPE_PKCS_SIGNED_DATA:
        return info
    content_type, signed_data = _walk_signed_data(der)
    info["content_type"] = content_type
    digest_algorithms = []
    certificate_count = 0
    signer_count = 0
    digest_seen = False
    for tag, cs, ce in signed_data:
        children = list(iter_children(der, cs, ce))
        if tag == 0x31 and not digest_seen:
            # digestAlgorithms is the SET that follows the version field.
            digest_seen = True
            for _at, as_, ae in children:
                oid = _first_oid(der, as_, ae)
                if oid:
                    digest_algorithms.append(OID_NAMES.get(oid, oid))
        elif tag == 0xA0:
            # certificates is an explicit [0] whose content is a SET OF.
            certificate_count = sum(1 for _ in iter_children(der, cs, ce))
        elif tag == 0xA1:
            # signerInfos written with an explicit [1] wrapper.
            signer_count = sum(1 for _ in iter_children(der, cs, ce))
        elif tag == 0x31 and digest_seen:
            # signerInfos written as [1] IMPLICIT SET OF, i.e. re-tagged as SET.
            signer_count = sum(1 for _ in children)
    info["digest_algorithms"] = digest_algorithms
    info["certificate_count"] = certificate_count
    info["signer_count"] = signer_count
    return info


def _empty() -> dict:
    return {
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
