#!/usr/bin/env python3
"""Terminal-style animated GIF of GeoWire's 3-source merge (your data + Google + OSM).
Self-contained: Pillow only. Values are from a real run (SF Blue Bottle).
"""
import os
from PIL import Image, ImageDraw, ImageFont

BG=(13,17,23); BAR=(22,27,34); DOTR=(255,95,86); DOTY=(255,189,46); DOTG=(39,201,63)
WHITE=(233,239,245); DIM=(128,137,148); DIMMER=(90,98,108)
CYAN=(86,182,194); GREEN=(126,231,135); PURPLE=(198,160,246); GOLD=(229,192,123)

font=ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf",22)
fontb=ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf",22)
FS=22; CW=font.getlength("M"); LH=FS+8; PAD_X=26; PAD_TOP=58; BAR_H=40; COLS=66
W=int(PAD_X*2+CW*COLS)

def new_frame():
    img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    d.rectangle([0,0,W,BAR_H],fill=BAR)
    for i,c in enumerate((DOTR,DOTY,DOTG)):
        cx=20+i*22; d.ellipse([cx,BAR_H//2-6,cx+12,BAR_H//2+6],fill=c)
    d.text((W/2,BAR_H/2),"geowire - merge",font=font,fill=DIMMER,anchor="mm")
    return img,d

def line(d,row,spans):
    x=PAD_X; y=PAD_TOP+row*LH
    for text,color,bold in spans:
        d.text((x,y),text,font=(fontb if bold else font),fill=color); x+=CW*len(text)

PROMPT=("$ ",CYAN,True)
CMD='geowire search "Blue Bottle Coffee" --strategy merge'

# 출처 색: internal=cyan, google=gold, nominatim=purple
BLOCKS=[
 [("  providers: ",DIMMER,False),("internal",CYAN,False),(" + ",DIMMER,False),("google",GOLD,False),(" + ",DIMMER,False),("nominatim",PURPLE,False),("  (GEOWIRE_CONFIG)",DIMMER,False)],
 None,
 [("● ",GREEN,True),("3 sources merged into 1 record",WHITE,True),("  ·  dedup 18->9  ·  $0.032",DIMMER,False)],
 None,
 [("Blue Bottle Coffee - HQ Flagship (our #1 store)",CYAN,True)],
 [("  rating 4.6/5   ·   (510) 661-3510",GOLD,False)],
 [("  Linden Street, San Francisco, California, 94102, US",GOLD,False)],
 None,
 [("which source gave which field:",DIM,True)],
 [("  internal   ",CYAN,True),("-> name",DIM,False),("             your store DB (authoritative)",DIMMER,False)],
 [("  google     ",GOLD,True),("-> rating, phone, address",DIM,False)],
 [("  nominatim  ",PURPLE,True),("-> location",DIM,False),("           OpenStreetMap",DIMMER,False)],
]
H=int(PAD_TOP+LH*(len(BLOCKS)+2)+16)

def render(cmd_len,out_stage,cursor):
    img,d=new_frame()
    typed=CMD[:cmd_len]
    spans=[PROMPT,(typed,WHITE,False)]
    # 쿼리 부분 초록 강조 (따옴표 안)
    line(d,0,spans)
    if cursor:
        cx=PAD_X+CW*(2+len(typed)); d.rectangle([cx,PAD_TOP+3,cx+CW-2,PAD_TOP+FS+2],fill=(120,130,140))
    r,shown=2,0
    for b in BLOCKS:
        if shown>=out_stage: break
        if b is None: r+=1; continue
        line(d,r,b); r+=1; shown+=1
    return img

frames,durations=[],[]
def add(img,ms):
    frames.append(img.convert("P",palette=Image.ADAPTIVE,colors=128)); durations.append(ms)

for _ in range(2): add(render(0,0,True),350)
i=0
while i<len(CMD):
    i=min(i+2,len(CMD)); add(render(i,0,True),50)
add(render(len(CMD),0,True),450); add(render(len(CMD),0,False),200)
nb=sum(1 for b in BLOCKS if b is not None)
for stage in range(1,nb+1): add(render(len(CMD),stage,False),230)
add(render(len(CMD),nb,False),3200)

out_dir=r"D:\DEV\App\Small\GeoRelay\docs\media"
os.makedirs(out_dir,exist_ok=True)
out=os.path.join(out_dir,"geowire-merge.gif")
frames[0].save(out,save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True,disposal=2)
render(len(CMD),nb,False).save(os.path.join(os.path.dirname(__file__),"preview_merge.png"))
print("WROTE",out,W,"x",H,"frames:",len(frames))
