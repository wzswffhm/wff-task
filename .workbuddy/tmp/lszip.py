# -*- coding: utf-8 -*-
"""列出 zip 内容（名称 / 大小 / Unix 权限 / CRC）。"""
import sys
import zipfile

p = sys.argv[1]
z = zipfile.ZipFile(p)
print(f"== {p}  entries={len(z.namelist())}  size={__import__('os').path.getsize(p)} B ==")
for n in z.namelist():
    i = z.getinfo(n)
    mode = (i.external_attr >> 16) & 0xFFFF
    print(f"{mode:o}\t{i.file_size:>9}\t{i.CRC:08X}\t{n}")
