#!/usr/bin/env python3
"""Render a terminal-style animated GIF of `geowire search`.
Self-contained: Pillow only. Reproduces a real geowire CLI run (all-Latin output).
"""
import os
from PIL import Image, ImageDraw, ImageFont

# ---- palette (GitHub dark) ----
BG    = (13, 17, 23)
BAR   = (22, 27, 34)
DOTR  = (255, 95, 86)
DOTY  = (255, 189, 46)
DOTG  = (39, 201, 63)
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
PAD_X = 26
PAD_TOP = 58
BAR_H = 40
COLS = 82

W = int(PAD_X * 2 + CW * COLS)
H = int(PAD_TOP + LH * 10 + 18)

def new_frame():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, BAR_H], fill=BAR)
    for i, c in enumerate((DOTR, DOTY, DOTG)):
        cx = 20 + i * 22
        d.ellipse([cx, BAR_H//2 - 6, cx + 12, BAR_H//2 + 6], fill=c)
    d.text((W/2, BAR_H/2), "geowire — zsh", font=font, fill=DIMMER, anchor="mm")
    return img, d

def draw_line(d, row, spans):
    x = PAD_X
    y = PAD_TOP + row * LH
    for text, color, bold in spans:
        d.text((x, y), text, font=(fontb if bold else font), fill=color)
        x += CW * len(text)

PROMPT  = ("$ ", CYAN, True)
CMD_PRE = 'npx @geowirehq/cli search '
CMD_ARG = '"Eiffel Tower"'

SUMMARY = [("Found 2 places", GREEN, True), (" · ", DIMMER, False),
           ("first-success", DIM, False), (" · ", DIMMER, False),
           ("nominatim", DIM, False), (" · ", DIMMER, False),
           ("1208ms", YELLOW, False)]
HEAD = [("#  Name          Distance  Address                                   Sources", DIM, True)]
SEP  = [("─  ────────────  ────────  ────────────────────────────────────────  ─────────", DIMMER, False)]
ROW1 = [("1  ", DIM, False), ("Tour Eiffel", WHITE, True),
        ("   -         Tour Eiffel, 5, Avenue Anatole France, …  ", DIM, False),
        ("nominatim", PURPLE, False)]
ROW2 = [("2  ", DIM, False), ("Eiffel Tower", WHITE, True),
        ("  -         Eiffel Tower, Improvement District No. …  ", DIM, False),
        ("nominatim", PURPLE, False)]
ATTR = [("Attribution: © OpenStreetMap contributors", DIMMER, False)]

# output blocks (None = blank spacer row)
BLOCKS = [SUMMARY, None, HEAD, SEP, ROW1, ROW2, None, ATTR]

def render(cmd_len, out_stage, cursor):
    img, d = new_frame()
    full = CMD_PRE + CMD_ARG
    typed = full[:cmd_len]
    spans = [PROMPT]
    if len(typed) <= len(CMD_PRE):
        spans.append((typed, WHITE, False))
    else:
        spans.append((CMD_PRE, WHITE, False))
        spans.append((typed[len(CMD_PRE):], GREEN, False))
    draw_line(d, 0, spans)
    if cursor:
        cx = PAD_X + CW * (2 + len(typed))
        d.rectangle([cx, PAD_TOP + 3, cx + CW - 2, PAD_TOP + FS + 2], fill=(120, 130, 140))
    r, shown = 2, 0
    for b in BLOCKS:
        if shown >= out_stage:
            break
        if b is None:
            r += 1
            continue
        draw_line(d, r, b)
        r += 1
        shown += 1
    return img

frames, durations = [], []
def add(img, ms):
    frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    durations.append(ms)

full = CMD_PRE + CMD_ARG
for _ in range(2):
    add(render(0, 0, True), 350)
i = 0
while i < len(full):
    i = min(i + 2, len(full))
    add(render(i, 0, True), 55)
add(render(len(full), 0, True), 500)
add(render(len(full), 0, False), 220)
n_blocks = sum(1 for b in BLOCKS if b is not None)
for stage in range(1, n_blocks + 1):
    add(render(len(full), stage, False), 240)
add(render(len(full), n_blocks, False), 2800)

out_dir = r"D:\DEV\App\Small\GeoRelay\docs\media"
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "geowire-search.gif")
frames[0].save(out, save_all=True, append_images=frames[1:],
               duration=durations, loop=0, optimize=True, disposal=2)
render(len(full), n_blocks, False).save(os.path.join(os.path.dirname(__file__), "preview_final.png"))
print("WROTE", out, W, "x", H, "frames:", len(frames))
