# wpeimg workspace

`wpeimg` reads Windows portable executable images and reports what is inside
them: the machine the image targets, where its sections live, where a relative
virtual address ends up in the file, and whether the recorded checksum still
matches the bytes.

## Layout

| Path | What it is |
| --- | --- |
| `wpeimg/` | the package under change |
| `assets/` | frozen images the tool is expected to describe correctly |
| `docs/FORMAT.md` | field notes taken while the tool was written |
| `tests/` | the smoke tests that ship with the package |

## Running things

```
python -m pytest tests/ -q
python -c "from wpeimg import inspect; print(inspect(open('assets/i386-module.bin','rb').read()))"
```

No network access is available and no dependency outside the standard library
is required at runtime.

## Samples

`assets/amd64-module.bin` is a real 64-bit module taken from a Windows
distribution. `assets/i386-module.bin` is a small 32-bit console image built by
hand so that both header layouts stay covered. Both are read-only inputs: the
tool must describe them, not rewrite them.
