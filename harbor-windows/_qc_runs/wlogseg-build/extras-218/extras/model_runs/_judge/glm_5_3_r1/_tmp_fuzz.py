"""Temporary fuzz/differential check (deleted before submit)."""

import io
import random

from wlogseg import WSegError, iter_segments, pack, read_all, unpack, verify

random.seed(20240607)

sample = open("assets/sample.wlsg", "rb").read()

# --- build a pile of valid containers
containers = [sample, open("assets/sample_empty.wlsg", "rb").read()]
for _ in range(60):
    n = random.randint(0, 6)
    segs = []
    for _i in range(n):
        segs.append((random.randint(0, 0xFFFF), bytes(random.randrange(256) for _ in range(random.randint(0, 40)))))
    containers.append(pack(segs))

for blob in containers:
    assert verify(blob) is True
    assert unpack(blob) == read_all(io.BytesIO(blob))

# --- corrupt them in every way imaginable and compare paths
bad_count = 0
diff = 0
for blob in containers:
    for _ in range(60):
        out = bytearray(blob)
        mode = random.randrange(5)
        if mode == 0:  # flip random byte
            out[random.randrange(len(out))] ^= 1 << random.randrange(8)
        elif mode == 1:  # truncate
            out = out[:random.randrange(len(out) + 1)]
        elif mode == 2:  # append junk
            out += bytes(random.randrange(256) for _ in range(random.randint(1, 9)))
        elif mode == 3:  # random header field surgery
            out[random.randrange(4, 16)] = random.randrange(256)
        else:  # splice
            if len(out) > 2:
                a = random.randrange(len(out))
                b = random.randrange(len(out))
                out[a], out[b] = out[b], out[a]
        bad = bytes(out)

        try:
            verify(bad)
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"verify raised {exc!r} for {bad!r}")

        kinds = []
        for fn in (lambda: unpack(bad), lambda: read_all(io.BytesIO(bad))):
            try:
                fn()
                kinds.append(None)
            except WSegError as exc:
                kinds.append(exc.kind)
            except Exception as exc:  # noqa: BLE001
                kinds.append(f"WRONG-TYPE:{type(exc).__name__}")

        if kinds[0] != kinds[1]:
            # only known, intentional difference: trailing junk is only
            # detectable when the total size is known (buffer path)
            if not (kinds[0] == "structure" and kinds[1] is None):
                diff += 1
                print("DIVERGENCE", kinds, bad.hex())
        if kinds[0] is None and verify(bad) is not True:
            raise AssertionError("unpack ok but verify False")
        if kinds[0] is not None and verify(bad) is not False:
            raise AssertionError("unpack failed but verify True")
        if kinds[0] is not None:
            bad_count += 1

print(f"containers: {len(containers)}, corrupt variants checked, "
      f"{bad_count} rejected, divergences: {diff}")

# --- pure random garbage never crashes anything
for _ in range(3000):
    blob = bytes(random.randrange(256) for _ in range(random.randint(0, 80)))
    assert verify(blob) is False
    for fn in (lambda: unpack(blob), lambda: read_all(io.BytesIO(blob))):
        try:
            fn()
        except WSegError:
            pass
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"{type(exc).__name__}: {exc}")

# --- random garbage that starts like a header
for _ in range(3000):
    blob = b"WLSG" + bytes(random.randrange(256) for _ in range(random.randint(0, 60)))
    assert verify(blob) is False
    try:
        unpack(blob)
    except WSegError as exc:
        assert exc.kind in ("magic", "version", "truncated", "structure", "checksum"), exc.kind
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{type(exc).__name__}: {exc}")

# --- huge declared length must not blow up memory (bounded reads)
evil = bytearray(pack([(1, b"abc")]))
evil[20:24] = (0xFFFFFFF0).to_bytes(4, "little")  # body_len of segment 0
try:
    read_all(io.BytesIO(bytes(evil)))
    raise AssertionError("evil container accepted")
except WSegError as exc:
    print("evil body_len ->", exc.kind)

print("FUZZ OK")
