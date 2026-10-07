Fixed three NTFS alternate data stream issues in wdl:

1. **archive.py**: Modified `copy_file` to copy PORTABLE_STREAMS after the main file copy. After `shutil.copy2`, the function now iterates through streams and uses `read_stream`/`write_stream` to preserve them. This ensures `Zone.Identifier` is carried over during archival.

2. **streams.py**: Fixed `stream_size` to call `os.path.getsize()` on the stream path instead of the main file path, returning the actual stream byte count rather than main file size.

3. **unblock.py**: Changed `unblock` to use the existing `remove_stream` function instead of calling `os.remove` directly. This makes it idempotent—returning False when the stream doesn't exist rather than raising FileNotFoundError.

All changes use only standard library functions and preserve existing public APIs. The fixes ensure archived files retain security marks, size calculations are accurate, and batch unblocking scripts don't crash on clean files.