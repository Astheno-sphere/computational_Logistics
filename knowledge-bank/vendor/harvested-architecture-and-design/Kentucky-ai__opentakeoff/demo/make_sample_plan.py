#!/usr/bin/env python3
"""Generate a synthetic demo floor plan for OpenTakeoff — fully original, no
copyright. Produces a tabloid sheet with four enclosed rooms (so One-Click Area
works), room labels (text must NOT block the fill), a sheet number, and a drawn
scale note in the title block (so auto-scale-detect works).

Run:  python3 make_sample_plan.py   ->   sample-plan.pdf
"""

W, H = 1224, 792  # 17" x 11" at 72pt/in


def content() -> bytes:
    ops = [
        "q",
        "3 w 0 0 0 RG",
        # outer building wall
        "120 110 980 580 re S",
        # interior partitions form a 2x2 of rooms
        "610 110 m 610 690 l S",
        "120 400 m 1100 400 l S",
        # room labels — glyphs are text ops, they don't bound the flood fill
        "BT /F1 22 Tf 300 250 Td (OFFICE 101) Tj ET",
        "BT /F1 22 Tf 820 250 Td (OFFICE 102) Tj ET",
        "BT /F1 22 Tf 300 560 Td (BREAK 103) Tj ET",
        "BT /F1 22 Tf 800 560 Td (CORRIDOR 104) Tj ET",
        # title block (lower-right): sheet number + drawn scale
        "BT /F1 32 Tf 985 150 Td (A-101) Tj ET",
        'BT /F1 16 Tf 865 118 Td (SCALE: 1/4" = 1\'-0") Tj ET',
        "Q",
    ]
    return ("\n".join(ops)).encode("latin-1")


def build() -> bytes:
    stream = content()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] "
         f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>").encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objects) + 1
    out += b"xref\n0 " + str(n).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\n"
            b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n")
    return out


if __name__ == "__main__":
    import os
    path = os.path.join(os.path.dirname(__file__), "sample-plan.pdf")
    with open(path, "wb") as f:
        f.write(build())
    print(f"wrote {path}")
