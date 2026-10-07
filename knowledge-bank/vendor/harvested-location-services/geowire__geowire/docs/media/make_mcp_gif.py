#!/usr/bin/env python3
"""Terminal-style animated GIF of the geowire MCP server (stdio).
Self-contained: Pillow only. Reproduces a real MCP tools/list + geocode_address call.
"""
import os
from PIL import Image, ImageDraw, ImageFont

BG    = (13, 17, 23)
BAR   = (22, 27, 34)
DOTR  = (255, 95, 86); DOTY = (255, 189, 46); DOTG = (39, 201, 63)
WHITE = (233, 239, 245)
DIM   = (128, 137, 148)
DIMMER= (90, 98, 108)
CYAN  = (86, 182, 194)
GREEN = (126, 231, 135)
PURPLE= (198, 160, 246)
YELLOW= (229, 192, 123)

font  = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 22)
fontb = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 22)
FS = 22
CW = font.getlength("M")
LH = FS + 8
PAD_X = 26; PAD_TOP = 58; BAR_H = 40; COLS = 60

W = int(PAD_X * 2 + CW * COLS)

def new_frame():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, BAR_H], fill=BAR)
    for i, c in enumerate((DOTR, DOTY, DOTG)):
        cx = 20 + i * 22
        d.ellipse([cx, BAR_H//2 - 6, cx + 12, BAR_H//2 + 6], fill=c)
    d.text((W/2, BAR_H/2), "geowire — mcp", font=font, fill=DIMMER, anchor="mm")
    return img, d

def draw_line(d, row, spans):
    x = PAD_X; y = PAD_TOP + row * LH
    for text, color, bold in spans:
        d.text((x, y), text, font=(fontb if bold else font), fill=color)
        x += CW * len(text)

PROMPT  = ("$ ", CYAN, True)
CMD     = 'npx -y @geowirehq/mcp'

def bullet(name, desc):
    return [("  • ", DIMMER, False), (name.ljust(19), CYAN, False), (desc, DIM, False)]

BLOCKS = [
    [("● ", GREEN, True), ("MCP server ready · stdio · providers: ", DIM, False), ("nominatim", WHITE, False)],
    None,
    [("▸ ", YELLOW, True), ("tools/list", WHITE, True)],
    [("◂ ", CYAN, True), ("5 tools", GREEN, True)],
    bullet("search_places",     "find places near a point"),
    bullet("get_place",         "full details by id"),
    bullet("geocode_address",   "address → coordinates"),
    bullet("reverse_geocode",   "coordinates → address"),
    bullet("list_geo_providers","what's configured"),
    None,
    [("▸ ", YELLOW, True), ("geocode_address ", WHITE, True), ("{ address: ", DIM, False), ('"Colosseum, Rome"', GREEN, False), (" }", DIM, False)],
    [("◂ ", CYAN, True), ("Colosseo", WHITE, True), ("  ·  ", DIMMER, False), ("41.89094, 12.49190", YELLOW, False)],
    [("  Colosseo, Municipio Roma I, Roma, 00184, Italia", DIM, False)],
    [("  ", DIM, False), ("nominatim:way/215801333", PURPLE, False), ("  ·  480ms", DIMMER, False)],
]
N_ROWS = sum(1 for b in BLOCKS if b is not None) + sum(1 for b in BLOCKS if b is None)
H = int(PAD_TOP + LH * (len(BLOCKS) + 2) + 16)

def render(cmd_len, out_stage, cursor):
    img, d = new_frame()
    typed = CMD[:cmd_len]
    spans = [PROMPT, (typed, WHITE, False)]
    draw_line(d, 0, spans)
    if cursor:
        cx = PAD_X + CW * (2 + len(typed))
        d.rectangle([cx, PAD_TOP + 3, cx + CW - 2, PAD_TOP + FS + 2], fill=(120, 130, 140))
    r, shown = 2, 0
    for b in BLOCKS:
        if shown >= out_stage:
            break
        if b is None:
            r += 1; continue
        draw_line(d, r, b)
        r += 1; shown += 1
    return img

frames, durations = [], []
def add(img, ms):
    frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    durations.append(ms)

for _ in range(2):
    add(render(0, 0, True), 350)
i = 0
while i < len(CMD):
    i = min(i + 2, len(CMD))
    add(render(i, 0, True), 55)
add(render(len(CMD), 0, True), 450)
add(render(len(CMD), 0, False), 200)
n_blocks = sum(1 for b in BLOCKS if b is not None)
for stage in range(1, n_blocks + 1):
    add(render(len(CMD), stage, False), 210)
add(render(len(CMD), n_blocks, False), 3000)

out_dir = r"D:\DEV\App\Small\GeoRelay\docs\media"
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "geowire-mcp.gif")
frames[0].save(out, save_all=True, append_images=frames[1:],
               duration=durations, loop=0, optimize=True, disposal=2)
render(len(CMD), n_blocks, False).save(os.path.join(os.path.dirname(__file__), "preview_mcp.png"))
print("WROTE", out, W, "x", H, "frames:", len(frames))
