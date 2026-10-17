# -*- coding: utf-8 -*-
"""把大文件按 block_size 切成 part_000.bin、part_001.bin ... 供飞书分片上传使用。

用法: python slice_for_upload.py <源文件> <输出目录> <block_size>
输出: 切片数量

单独成文件而不是用 `python -c`，是因为 PowerShell 5.1 把多行代码经 -c 传给
python.exe 时会破坏其中的换行与双引号，导致 "<string>" 语法错误。
"""
import pathlib
import sys


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    block = int(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    # 清掉上一次的残留，避免旧分片被误传
    for old in out.glob("part_*.bin"):
        old.unlink()
    count = 0
    with src.open("rb") as fh:
        while True:
            chunk = fh.read(block)
            if not chunk:
                break
            (out / ("part_%03d.bin" % count)).write_bytes(chunk)
            count += 1
    print(count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
