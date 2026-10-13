# -*- coding: utf-8 -*-
"""probe_authenticode.py -- 摸清真实 Authenticode blob 的 DER 结构，用于设计 219 v1.3.0 判据。

用法：python probe_authenticode.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

ASSETS = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
              r"\relaunch-20261013\staged\wfflab__wpeimg-219-v1.2.0-delivery"
              r"\environment\workspace\assets")

OID_SHA256 = "2.16.840.1.101.3.4.2.1"
OID_SHA1 = "1.3.14.3.2.26"
OID_SHA384 = "2.16.840.1.101.3.4.2.2"
OID_SHA512 = "2.16.840.1.101.3.4.2.3"


def decode_oid(raw: bytes) -> str:
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


def read_tlv(buf: bytes, offset: int):
    if offset + 2 > len(buf):
        raise ValueError("truncated header")
    tag = buf[offset]
    length = buf[offset + 1]
    header = 2
    if length & 0x80:
        count = length & 0x7F
        if count == 0 or offset + 2 + count > len(buf):
            raise ValueError("bad length")
        length = int.from_bytes(buf[offset + 2:offset + 2 + count], "big")
        header = 2 + count
    start = offset + header
    end = start + length
    if end > len(buf):
        raise ValueError("truncated content")
    return tag, start, end, end


def children(buf, start, end):
    out = []
    pos = start
    while pos < end:
        tag, cs, ce, nxt = read_tlv(buf, pos)
        out.append((tag, cs, ce))
        pos = nxt
        if nxt <= pos - 1 and nxt == pos:
            break
    return out


def main() -> int:
    blob = (ASSETS / "amd64-module.bin").read_bytes()
    nt = struct.unpack_from("<I", blob, 0x3C)[0]
    opt = nt + 24
    plus = struct.unpack_from("<H", blob, opt)[0] == 0x20B
    diroff = opt + (112 if plus else 96)
    cert_off, cert_size = struct.unpack_from("<II", blob, diroff + 4 * 8)
    sig = blob[cert_off:cert_off + cert_size]
    dw_len, w_rev, w_type = struct.unpack_from("<IHH", sig, 0)
    der = sig[8:dw_len]
    print("WIN_CERTIFICATE: dwLength=%d wRevision=0x%04X wCertificateType=0x%04X"
          % (dw_len, w_rev, w_type))
    print("DER length=%d" % len(der))

    tag, s, e, _ = read_tlv(der, 0)
    print("outer tag=0x%02X len=%d" % (tag, e - s))
    kids = children(der, s, e)
    print("outer children:", [(hex(t), ce - cs) for t, cs, ce in kids])
    # ContentInfo: [0]=OID contentType, [1]=[0] explicit content
    oid_tag, oid_s, oid_e = kids[0]
    print("  contentType OID:", decode_oid(der[oid_s:oid_e]))
    a0_tag, a0_s, a0_e = kids[1]
    print("  explicit tag=0x%02X" % a0_tag)
    inner_tag, in_s, in_e, _ = read_tlv(der, a0_s)
    print("  signedData SEQUENCE len=%d" % (in_e - in_s))
    sd = children(der, in_s, in_e)
    print("  signedData children:", [(hex(t), ce - cs) for t, cs, ce in sd])
    ver_tag, ver_s, ver_e = sd[0]
    print("  version=%d" % int.from_bytes(der[ver_s:ver_e], "big"))
    da_tag, da_s, da_e = sd[1]
    print("  digestAlgorithms SET len=%d, count=%d" % (da_e - da_s, len(children(der, da_s, da_e))))
    for _t, cs, ce in children(der, da_s, da_e):
        algs = children(der, cs, ce)
        ot, os_, oe = algs[0]
        print("     digest OID:", decode_oid(der[os_:oe]))
    # find [0] certificates and [1] signerInfos context tags
    for t, cs, ce in sd:
        if t == 0xA0:
            certs = children(der, cs, ce)
            print("  certificates [0]: count=%d kinds=%s"
                  % (len(certs), sorted({hex(x[0]) for x in certs})))
        if t == 0xA1:
            sis = children(der, cs, ce)
            print("  signerInfos [1]: count=%d" % len(sis))
            for _st, ss, se in sis:
                fields = children(der, ss, se)
                print("     SignerInfo children:", [(hex(x[0]), x[2] - x[1]) for x in fields])
                # issuerAndSerialNumber is a SEQUENCE
                for ft, fs, fe in fields:
                    if ft == 0x30:
                        sub = children(der, fs, fe)
                        print("       issuerAndSerialNumber parts:",
                              [(hex(x[0]), x[2] - x[1]) for x in sub])
                        if len(sub) >= 2:
                            it, iss, ie = sub[0]
                            sn_t, sns, sne = sub[1]
                            print("       issuer(rdn) len=%d  serial_int=%s len=%d"
                                  % (ie - iss, der[sns:sne].hex(), sne - sns))
                        break
    return 0


if __name__ == "__main__":
    sys.exit(main())
