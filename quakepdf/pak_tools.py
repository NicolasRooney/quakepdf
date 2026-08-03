#!/usr/bin/env python3
"""
Quake PAK utilities.

strip : rebuild a PAK without the lumps we can never use in a PDF
        (sounds, CD tracks, demos). There is no audio device behind a
        PDF form field, so every byte of .wav is dead weight.
embed : emit a JS file declaring `embedded_files` with base64 payloads.
"""

import argparse
import base64
import os
import struct
import sys

HEADER = struct.Struct("<4sii")
ENTRY = struct.Struct("<56sii")

DROP_PREFIXES = ("sound/",)
DROP_SUFFIXES = (".wav", ".dem")

BRUSH_MODEL_PREFIX = "maps/b_"

BRUSH_MODELS = {
    "b_shell0", "b_shell1", "b_nail0", "b_nail1", "b_rock0", "b_rock1",
    "b_batt0", "b_batt1", "b_bh10", "b_bh25", "b_bh100", "b_explob",
    "b_exbox2",
}


def is_level(name):
    """True for a playable map, False for an item brush model."""
    low = name.lower()
    if not low.startswith("maps/") or not low.endswith(".bsp"):
        return False
    return not low.startswith(BRUSH_MODEL_PREFIX)


def read_pak(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, diroff, dirlen = HEADER.unpack_from(data, 0)
    if magic != b"PACK":
        raise SystemExit(f"{path}: not a Quake PAK (magic={magic!r})")
    n = dirlen // ENTRY.size
    entries = []
    for i in range(n):
        raw, pos, ln = ENTRY.unpack_from(data, diroff + i * ENTRY.size)
        name = raw.split(b"\0")[0].decode("latin1")
        entries.append((name, data[pos:pos + ln]))
    return entries


def write_pak(path, entries):
    body = bytearray()
    dir_records = []
    for name, blob in entries:
        dir_records.append((name, HEADER.size + len(body), len(blob)))
        body += blob
    diroff = HEADER.size + len(body)
    with open(path, "wb") as f:
        f.write(HEADER.pack(b"PACK", diroff, len(dir_records) * ENTRY.size))
        f.write(body)
        for name, pos, ln in dir_records:
            f.write(ENTRY.pack(name.encode("latin1")[:55].ljust(56, b"\0"), pos, ln))


def should_drop(name, keep_demos):
    low = name.lower()
    if low.startswith(DROP_PREFIXES):
        return True
    if low.endswith(".wav"):
        return True
    if not keep_demos and low.endswith(".dem"):
        return True
    return False


def cmd_strip(args):
    entries = read_pak(args.src)
    before = sum(len(b) for _, b in entries)

    kept, dropped = [], []
    for name, blob in entries:
        (dropped if should_drop(name, args.keep_demos) else kept).append((name, blob))

    if args.only_maps:
        wanted = set(args.only_maps)
        filtered = []
        for name, blob in kept:
            if is_level(name):
                base = os.path.basename(name.lower())[:-4]
                if base not in wanted:
                    dropped.append((name, blob))
                    continue
            filtered.append((name, blob))
        kept = filtered

    present = {os.path.basename(n.lower())[:-4] for n, _ in kept
               if n.lower().startswith(BRUSH_MODEL_PREFIX)}
    missing = BRUSH_MODELS - present
    if missing:
        print(f"  WARNING: {len(missing)} item brush model(s) absent from the "
              f"source PAK: {' '.join(sorted(missing))}")
        print("           Levels that spawn those items will die in "
              "Mod_NumForName.")
        print("           Regenerate them with mkbmodels.py, then add them "
              "with pakpatch.py.")

    write_pak(args.dst, kept)
    after = sum(len(b) for _, b in kept)
    print(f"  kept    {len(kept):5d} lumps  {before/1048576:7.2f} MB -> {after/1048576:.2f} MB")
    print(f"  dropped {len(dropped):5d} lumps  "
          f"({sum(len(b) for _, b in dropped)/1048576:.2f} MB)")
    print(f"  wrote {args.dst} ({os.path.getsize(args.dst)/1048576:.2f} MB)")


def cmd_embed(args):
    parts = []
    total = 0
    for spec in args.files:
        if "=" in spec:
            vpath, real = spec.split("=", 1)
        else:
            real = spec
            vpath = "id1/" + os.path.basename(spec)
        with open(real, "rb") as f:
            blob = f.read()
        b64 = base64.b64encode(blob).decode()
        total += len(b64)
        parts.append('{name:"%s",b64:"%s"}' % (vpath, b64))
        print(f"  embed {vpath}: {len(blob)/1048576:.2f} MB "
              f"-> {len(b64)/1048576:.2f} MB base64", file=sys.stderr)

    with open(args.out, "w") as f:
        f.write("var embedded_files = [" + ",".join(parts) + "];\n")
    print(f"  wrote {args.out} ({total/1048576:.2f} MB of base64)", file=sys.stderr)


def cmd_list(args):
    entries = read_pak(args.src)
    by_ext = {}
    for name, blob in entries:
        ext = os.path.splitext(name)[1].lower() or "(none)"
        s, c = by_ext.get(ext, (0, 0))
        by_ext[ext] = (s + len(blob), c + 1)
    total = sum(len(b) for _, b in entries)
    print(f"{args.src}: {len(entries)} lumps, {total/1048576:.2f} MB")
    for ext, (size, count) in sorted(by_ext.items(), key=lambda kv: -kv[1][0]):
        print(f"  {ext:<8} {size/1048576:7.2f} MB  ({count} lumps)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("strip")
    s.add_argument("src")
    s.add_argument("dst")
    s.add_argument("--keep-demos", action="store_true")
    s.add_argument("--only-maps", nargs="*", default=None,
                   help="keep only these BSP basenames, e.g. e1m1 start")
    s.set_defaults(func=cmd_strip)

    e = sub.add_parser("embed")
    e.add_argument("out")
    e.add_argument("files", nargs="+", help="[virtualpath=]realpath")
    e.set_defaults(func=cmd_embed)

    l = sub.add_parser("list")
    l.add_argument("src")
    l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
