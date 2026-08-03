#!/usr/bin/env python3
"""
mkbmodels.py: generate the 13 maps/b_*.bsp item brush models.

Quake's item entities are brush models: progs.dat calls
precache_model("maps/b_shell0.bsp") for every ammo and health box.
PAK stripper filters on "maps/*.bsp" removes them along with the levels,
so spawn an item = failure in Mod_ForName.

If you have the original pak0.pak,
keep those lumps (see pak_tools.py --keep-brush-models).
This script exists for the case where only an already-stripped PAK survives:
it emits geometrically valid stand-ins at the sizes progs.dat expects.
At 320x200 in six ASCII it's not meaningfully different from the originals.
"""
import struct
import sys

from bsp29 import BSP, CONTENTS_EMPTY, CONTENTS_SOLID, newell

BOXES = {
    "b_shell0":  (32, 32, 16),
    "b_shell1":  (32, 32, 32),
    "b_nail0":   (32, 32, 16),
    "b_nail1":   (32, 32, 32),
    "b_rock0":   (32, 32, 16),
    "b_rock1":   (32, 32, 32),
    "b_batt0":   (32, 32, 16),
    "b_batt1":   (32, 32, 32),
    "b_bh10":    (32, 32, 16),
    "b_bh25":    (32, 32, 32),
    "b_bh100":   (32, 32, 32),
    "b_explob":  (32, 32, 64),
    "b_exbox2":  (32, 32, 32),
}

CORNERS = [(bx, by, bz) for bx in (0, 1) for by in (0, 1) for bz in (0, 1)]

TEXVECS = {
    0: ((0, 1, 0), (0, 0, -1)),
    1: ((1, 0, 0), (0, 0, -1)),
    2: ((1, 0, 0), (0, -1, 0)),
}

LIGHT_LEVEL = 170

def borrow_miptex(donor_bsp, wanted):
    """Pull one miptex out of a real map, complete with its mip chain."""
    for t in donor_bsp.textures():
        if t and t["name"] == wanted:
            size = t["w"] * t["h"] // 64 * 85
            blob = t["data"][t["base"]:t["base"] + 40 + size]
            out = bytearray(blob)
            struct.pack_into("<4I", out, 24, 40, 40 + t["w"] * t["h"],
                             40 + t["w"] * t["h"] * 5 // 4,
                             40 + t["w"] * t["h"] * 21 // 16)
            return bytes(out), t["w"], t["h"]
    raise KeyError(wanted)


def build_solid(mins, maxs, miptex, invert=False,
                entities=b'{\n"classname" "worldspawn"\n}\n\0'):
    """
    BSP29 file holding one axis-aligned brush.

    invert=False -> a solid box (an item model): faces point outward,
                    the interior is CONTENTS_SOLID.
    invert=True  -> a hollow room (a test level): faces point inward,
                    the interior is the one empty leaf.
    """
    import math
    b = BSP()
    lo = [float(v) for v in mins]
    hi = [float(v) for v in maxs]

    verts = [(hi[0] if bx else lo[0], hi[1] if by else lo[1],
              hi[2] if bz else lo[2]) for (bx, by, bz) in CORNERS]
    b.raw["vertexes"] = b"".join(struct.pack("<3f", *v) for v in verts)
    vindex = {c: i for i, c in enumerate(CORNERS)}

    planes = []
    for axis in range(3):
        n = [0.0, 0.0, 0.0]
        n[axis] = 1.0
        planes.append((tuple(n), lo[axis], axis))
        planes.append((tuple(n), hi[axis], axis))
    b.raw["planes"] = b"".join(struct.pack("<4fi", *n, dst, t)
                               for (n, dst, t) in planes)
    edges = [(0, 0)]
    edge_lookup = {}

    def edge_index(a, b_):
        if (a, b_) in edge_lookup:
            return edge_lookup[(a, b_)]
        if (b_, a) in edge_lookup:
            return -edge_lookup[(b_, a)]
        edges.append((vindex[a], vindex[b_]))
        edge_lookup[(a, b_)] = len(edges) - 1
        return len(edges) - 1

    faces, surfedges, texinfos, lighting = [], [], [], bytearray()

    for axis in range(3):
        for is_high in (0, 1):
            facing = 1.0 if is_high else -1.0
            if invert:
                facing = -facing
            outward = [0.0, 0.0, 0.0]
            outward[axis] = facing
            planenum = axis * 2 + is_high
            side = 0 if facing > 0 else 1

            quad = [c for c in CORNERS if c[axis] == is_high]
            u_ax, v_ax = [k for k in range(3) if k != axis]
            centre = (sum(c[u_ax] for c in quad) / 4.0,
                      sum(c[v_ax] for c in quad) / 4.0)
            quad.sort(key=lambda c: math.atan2(c[v_ax] - centre[1],
                                               c[u_ax] - centre[0]))
            pts = [verts[vindex[c]] for c in quad]
            if sum(a * b_ for a, b_ in zip(newell(pts), outward)) > 0:
                quad.reverse()

            first = len(surfedges)
            for i in range(4):
                surfedges.append(edge_index(quad[i], quad[(i + 1) % 4]))

            s_vec, t_vec = TEXVECS[axis]
            texinfos.append(struct.pack("<8f2i", *s_vec, 0.0, *t_vec, 0.0, 0, 0))

            span_u = int(hi[u_ax] - lo[u_ax])
            span_v = int(hi[v_ax] - lo[v_ax])
            smax = (span_u >> 4) + 1
            tmax = (span_v >> 4) + 1
            assert span_u <= 256 and span_v <= 256, "surface extents > 256"
            lightofs = len(lighting)
            lighting += bytes([LIGHT_LEVEL]) * (smax * tmax)

            faces.append(struct.pack("<hhihh4Bi", planenum, side, first, 4,
                                     len(texinfos) - 1,
                                     0, 255, 255, 255, lightofs))

    b.raw["edges"] = b"".join(struct.pack("<2H", *e) for e in edges)
    b.raw["surfedges"] = b"".join(struct.pack("<i", e) for e in surfedges)
    b.raw["faces"] = b"".join(faces)
    b.raw["texinfo"] = b"".join(texinfos)
    b.raw["lighting"] = bytes(lighting)
    b.raw["textures"] = struct.pack("<ii", 1, 8) + miptex

    inner = CONTENTS_EMPTY if invert else CONTENTS_SOLID
    outer = CONTENTS_SOLID if invert else CONTENTS_EMPTY

    nodes, leafs, marksurfaces = [], [], []
    leafs.append(struct.pack("<ii6h2H4B", CONTENTS_SOLID, -1,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    nlo = [int(v) - 16 for v in lo]
    nhi = [int(v) + 16 for v in hi]

    if invert:
        marksurfaces = list(range(6))
        leafs.append(struct.pack("<ii6h2H4B", CONTENTS_EMPTY, -1,
                                 nlo[0], nlo[1], nlo[2], nhi[0], nhi[1], nhi[2],
                                 0, 6, 0, 0, 0, 0))
        inner_child = -2
        outer_child = -1
    else:
        inner_child = -1

    for i in range(6):
        axis, is_high = divmod(i, 2)
        inside_front = (is_high == 0)
        if not invert:
            leafnum = len(leafs)
            marksurfaces.append(i)
            leafs.append(struct.pack("<ii6h2H4B", CONTENTS_EMPTY, -1,
                                     -4096, -4096, -4096, 4096, 4096, 4096,
                                     len(marksurfaces) - 1, 1, 0, 0, 0, 0))
            outer_child = -(leafnum + 1)
        nxt = (i + 1) if i < 5 else inner_child
        children = (nxt, outer_child) if inside_front else (outer_child, nxt)
        nodes.append(struct.pack("<i2h6h2H", i, children[0], children[1],
                                 nlo[0], nlo[1], nlo[2], nhi[0], nhi[1], nhi[2],
                                 i, 1))
    b.raw["nodes"] = b"".join(nodes)
    b.raw["leafs"] = b"".join(leafs)
    b.raw["marksurfaces"] = b"".join(struct.pack("<H", m) for m in marksurfaces)

    clip = []
    for i in range(6):
        axis, is_high = divmod(i, 2)
        inside_front = (is_high == 0)
        nxt = (i + 1) if i < 5 else inner
        children = (nxt, outer) if inside_front else (outer, nxt)
        clip.append(struct.pack("<i2h", i, children[0], children[1]))
    b.raw["clipnodes"] = b"".join(clip)

    b.raw["models"] = struct.pack("<9f7i", lo[0], lo[1], lo[2],
                                  hi[0], hi[1], hi[2], 0.0, 0.0, 0.0,
                                  0, 0, 0, 0, 1 if invert else 6, 0, 6)
    b.raw["entities"] = entities
    b.raw["visibility"] = b""
    return b.serialize()


def build_box(w, d, h, miptex):
    return build_solid((0, 0, 0), (w, d, h), miptex)


def main():
    donor_path, outdir = sys.argv[1], sys.argv[2]
    donor = BSP(open(donor_path, "rb").read())
    miptex, tw, th = borrow_miptex(donor, "slipside")
    print(f"texture borrowed from donor map: slipside {tw}x{th}, "
          f"{len(miptex)} bytes")
    import os
    os.makedirs(outdir, exist_ok=True)
    for name, (w, d, h) in sorted(BOXES.items()):
        data = build_box(w, d, h, miptex)
        open(f"{outdir}/{name}.bsp", "wb").write(data)
        print(f"  {name}.bsp  {w}x{d}x{h}  {len(data)} bytes")


if __name__ == "__main__":
    main()
