#!/usr/bin/env python3
"""
pakpatch.py: add files to a PAK, and re-embed a PAK into the compiled
JavaScript bundle.

  pakpatch.py add   <in.pak> <out.pak> <name=path> [name=path ...]
  pakpatch.py embed <bundle.js> <pak> <out.js>
"""
import base64
import struct
import sys


def read_pak(path):
    data = open(path, "rb").read()
    magic, off, size = struct.unpack("<4sii", data[:12])
    assert magic == b"PACK", "not a PAK"
    files = []
    for i in range(size // 64):
        e = data[off + i * 64: off + (i + 1) * 64]
        name = e[:56].split(b"\0")[0].decode("latin-1")
        fo, fl = struct.unpack("<ii", e[56:64])
        files.append((name, data[fo:fo + fl]))
    return files


def write_pak(path, files):
    body = bytearray(12)
    dirents = bytearray()
    for name, blob in files:
        ofs = len(body)
        body += blob
        while len(body) % 4:
            body += b"\0"
        nb = name.encode("latin-1")
        assert len(nb) < 56, name
        dirents += nb + b"\0" * (56 - len(nb)) + struct.pack("<ii", ofs, len(blob))
    diroff = len(body)
    body += dirents
    struct.pack_into("<4sii", body, 0, b"PACK", diroff, len(dirents))
    open(path, "wb").write(bytes(body))
    return len(body)


def cmd_add(argv):
    src, dst = argv[0], argv[1]
    files = read_pak(src)
    have = {n for n, _ in files}
    for spec in argv[2:]:
        name, path = spec.split("=", 1)
        blob = open(path, "rb").read()
        if name in have:
            files = [(n, b if n != name else blob) for n, b in files]
            print(f"  replaced {name} ({len(blob)} bytes)")
        else:
            files.append((name, blob))
            print(f"  added    {name} ({len(blob)} bytes)")
    total = write_pak(dst, files)
    print(f"{dst}: {len(files)} files, {total} bytes")


def cmd_embed(argv):
    bundle_path, pak_path, out_path = argv
    js = open(bundle_path, "rb").read()
    start = js.find(b'b64:"')
    assert start > 0, "no embedded_files literal found"
    start += len(b'b64:"')
    end = js.find(b'"', start)
    b64 = base64.b64encode(open(pak_path, "rb").read())
    out = js[:start] + b64 + js[end:]
    open(out_path, "wb").write(out)
    print(f"{out_path}: {len(out)} bytes "
          f"(payload {len(b64) / 1048576:.2f} MB of base64)")


if __name__ == "__main__":
    {"add": cmd_add, "embed": cmd_embed}[sys.argv[1]](sys.argv[2:])
