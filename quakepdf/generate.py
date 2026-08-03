#!/usr/bin/env python3
"""
generate.py: wrap the compiled JavaScript in a PDF.

The page is one AcroForm.
Output is RESY text fields, one per scanline;
input is a text field with a keystroke action plus a grid of pushbuttons;
the engine is driven by the page-open JavaScript action.

Usage: generate.py <compiled.js> <out.pdf> [--width 320] [--height 200]
"""
import argparse
import sys

PAGE_W, PAGE_H = 952, 620

FB_X0, FB_X1 = 0, 632
FB_TOP = PAGE_H
ROW_H = 2

CON_ROWS = 25
CON_X0, CON_X1 = 8, 628
CON_Y0, CON_ROW_H = 8, 8

PANEL_X0, PANEL_X1 = 644, 944
PANEL_TOP = 606
PANEL_BOTTOM = 228

BTN_W, BTN_H, BTN_GAP = 92, 28, 10

BUTTONS = [
    [("<trn", "q", 1), ("fwd", "w", 1), ("trn>", "e", 1)],
    [("<str", "a", 1), ("back", "s", 1), ("str>", "d", 1)],
    [("fire", " ", 2), ("jump", "f", 1)],
    [("esc", "x", 1), ("entr", "r", 1), ("tab", "z", 1)],
]

CONTROLS = [
    "W/S move, A/D strafe, Q/E turn",
    "space = fire, F = jump",
    "X = escape, R = enter, Z = tab",
]

FOOTER = [
    "Chromium-based browsers only.",
    "Made by nicolasrooney, inspired by ading2210's doompdf.",
    "Source Code: https://github.com/NicolasRooney/quakepdf",
]


def esc(s):
    """Escape a Python str for a PDF literal string."""
    return (s.replace("\\", r"\\")
             .replace("(", r"\(")
             .replace(")", r"\)")
             .replace("\r", r"\r"))


class Layout:
    """Top-down cursor for the right-hand panel."""

    def __init__(self, top):
        self.y = top
        self.text = []      # (x, y, size, string)

    def line(self, s, size=8, gap=4):
        self.y -= size
        self.text.append((PANEL_X0, self.y, size, s))
        self.y -= gap

    def space(self, n):
        self.y -= n

    def reserve(self, h):
        """Claim h units and return the bottom edge of the claimed block."""
        self.y -= h
        return self.y


def build(js, resx, resy):
    annots = []
    lay = Layout(PANEL_TOP)

    lay.line("QuakePDF", 24, gap=6)
    lay.line("", 8, gap=14)

    lay.line("Controls", 10, gap=6)
    for c in CONTROLS:
        lay.line(c, 8, gap=3)
    lay.space(12)

    lay.line("Click the box below, then type:", 8, gap=4)
    box_h = 24
    box_bottom = lay.reserve(box_h)
    annots.append(
        "<</AA <</K <</JS (key_pressed\\(event.change\\)) /S /JavaScript>>>> "
        "/BS <</W 0>> /FT /Tx /Ff 2 /Rect [%d %d %d %d] /Subtype /Widget "
        "/T (key_input) /Type /Annot /V (Click here, then type to play.)>>"
        % (PANEL_X0, box_bottom, PANEL_X1, box_bottom + box_h))
    lay.space(16)

    lay.line("Or use the buttons:", 8, gap=6)
    for row in BUTTONS:
        row_bottom = lay.reserve(BTN_H)
        x = PANEL_X0
        for label, key, span in row:
            w = BTN_W * span + BTN_GAP * (span - 1)
            annots.append(
                "<</AA <</D <</JS (key_down\\('%s'\\)) /S /JavaScript>> "
                "/U <</JS (key_up\\('%s'\\)) /S /JavaScript>>>> /BS <</W 0>> "
                "/FT /Btn /Ff 65536 /MK <</BG [0.9] /CA (%s)>> "
                "/Rect [%d %d %d %d] /Subtype /Widget /T (%s_button) "
                "/Type /Annot /V <>>>"
                % (esc(key), esc(key), esc(label), x, row_bottom,
                   x + w, row_bottom + BTN_H, esc(label)))
            x += w + BTN_GAP
        lay.space(BTN_GAP)

    lay.space(10)
    for f in FOOTER:
        lay.line(f, 8, gap=3)
        if "https://" in f:
            w = len(f) * 4.8 
            base_y = lay.y + 3 
            url = f.split("https://")[1]
            url = "https://" + url
            annots.append(
                "<</Type /Annot /Subtype /Link /Rect [%d %d %d %d] /Border [0 0 0] "
                "/A <</S /URI /URI (%s)>>>>"
                % (PANEL_X0, base_y - 2, PANEL_X0 + w, base_y + 8, esc(url))
            )

    if lay.y < PANEL_BOTTOM:
        sys.exit("panel overflowed: bottom is %d, limit %d" % (lay.y, PANEL_BOTTOM))

    for i in range(resy):
        y = FB_TOP - (i + 1) * ROW_H
        annots.append(
            "<</BS <</W 0>> /FT /Tx /Ff 2 /Rect [%d %d %d %d] /Subtype /Widget "
            "/T (field_%d) /Type /Annot /V <>>>"
            % (FB_X0, y, FB_X1, y + ROW_H, resy - 1 - i))

    for i in range(CON_ROWS):
        y = CON_Y0 + i * CON_ROW_H
        annots.append(
            "<</BS <</W 0>> /FT /Tx /Ff 2 /Rect [%d %d %d %d] /Subtype /Widget "
            "/T (console_%d) /Type /Annot /V <>>>"
            % (CON_X0, y, CON_X1, y + CON_ROW_H, i))

    parts = []
    for x, y, size, s in lay.text:
        parts.append("BT /F1 %d Tf %d %d Td (%s) Tj ET\n" % (size, x, y, esc(s)))
    content = "".join(parts)

    out = bytearray()
    offsets = {}

    def add(s):
        out.extend(s.encode("latin-1") if isinstance(s, str) else s)

    add("%PDF-1.3\n%\xe2\xe3\xcf\xd3\n")

    offsets[1] = len(out)
    add("1 0 obj\n<</Pages 2 0 R /Type /Catalog>>\nendobj\n")

    offsets[2] = len(out)
    add("2 0 obj\n<</Count 1 /Kids [3 0 R] /Type /Pages>>\nendobj\n")

    offsets[3] = len(out)
    add("3 0 obj\n<</AA <</O <</JS (")
    add(esc("try {" + js + "\n} catch (e) {app.alert(e.stack || e)}"))
    add(") /S /JavaScript>>>>\n/Annots [")
    add("\n".join(annots))
    add("]\n/Contents 4 0 R /MediaBox [0 0 %d %d] /Parent 2 0 R\n" % (PAGE_W, PAGE_H))
    add("/Resources <</Font <</F1 <</BaseFont /Courier /Subtype /Type1 "
        "/Type /Font>>>>>>\n/Type /Page>>\nendobj\n")

    offsets[4] = len(out)
    add("4 0 obj\n<</Length %d>>\nstream\n" % len(content))
    add(content)
    add("endstream\nendobj\n")

    startxref = len(out)
    add("xref\n0 5\n0000000000 65535 f \n")
    for i in range(1, 5):
        add("%010d 00000 n \n" % offsets[i])
    add("trailer\n<</Root 1 0 R /Size 5>>\nstartxref\n%d\n%%%%EOF\n" % startxref)
    return bytes(out), lay


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("js")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=200)
    a = ap.parse_args()

    js = open(a.js, "r", encoding="latin-1").read()
    pdf, lay = build(js, a.width, a.height)
    open(a.out, "wb").write(pdf)
    print("%s: %.2f MB, %dx%d, panel bottom at y=%d (limit %d)"
          % (a.out, len(pdf) / 1048576, a.width, a.height, lay.y, PANEL_BOTTOM))


if __name__ == "__main__":
    main()
