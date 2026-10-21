import json, math, random
random.seed(7)
S=json.load(open("robustfront.json"))
C={"ink":"#E8DFD0","mut":"#b89a86","gold":"#D4A530","sage":"#9DB886","terra":"#D4835C","red":"#C45545","teal":"#7CBAC4","line":"#5a3a40","bg":"#2b161c","dark":"#1f1014"}
ax=S["axes"]; xmn,xmx=ax["x"]["min"],ax["x"]["max"]; ymn,ymx=ax["y"]["min"],ax["y"]["max"]
# plot box
PX,PY,PW,PH=108,150,760,470
def sx(f): return PX+(f-xmn)/(xmx-xmn)*PW
def sy(m): return PY+(ymx-m)/(ymx-ymn)*PH
def c(f,m,r,fill,op=1,st="none",sw=0):
    s=f' stroke="{st}" stroke-width="{sw}"' if st!="none" else ""
    return f'<circle cx="{sx(f):.1f}" cy="{sy(m):.1f}" r="{r}" fill="{fill}" opacity="{op}"{s}/>'
E=[]
# generation ghost cloud (two faint streams converging to front) -> organic
for i in range(240):
    t=random.random()
    f=xmn+0.08+t*(xmx-xmn-0.10)
    spread=0.055*(1-t)+0.012
    m=(0.085-(f-0.55)/0.18*0.09 if f>0.42 else 0.0)-abs(random.gauss(0,spread))-0.01
    E.append(c(f,m,random.uniform(0.6,1.4),C["ink"],0.07))
# dominated (cream faint, larger)
for i in range(130):
    f=random.uniform(xmn+0.04,0.70); 
    top=0.085-(f-0.55)/0.18*0.09 if f>0.42 else 0.015
    m=random.uniform(ymn+0.01,min(top-0.005,0.055))
    E.append(c(f,m,random.uniform(1.4,2.6),C["ink"],0.26))
# near-optimal amber just inside front
for i in range(18):
    t=random.random(); f=0.50+t*0.21; m=(0.072-t*0.082)-random.uniform(0.004,0.016)
    E.append(c(f,m,4.3,C["gold"],0.9))
# front sage
front=[]
for i in range(27):
    t=i/26; f=0.555+t*(0.728-0.555); m=0.093-t*(0.093-(-0.014))-0.006*math.sin(t*3.1)
    front.append((f,m)); E.append(c(f,m,4.8,C["sage"],0.96))
# axes
A=[f'<line x1="{PX}" y1="{PY}" x2="{PX}" y2="{PY+PH}" stroke="{C["red"]}" stroke-width="1.5"/>',
   f'<line x1="{PX}" y1="{PY+PH}" x2="{PX+PW}" y2="{PY+PH}" stroke="{C["red"]}" stroke-width="1.5"/>']
for f in ax["x"]["ticks"]:
    A.append(f'<line x1="{sx(f):.0f}" y1="{PY+PH}" x2="{sx(f):.0f}" y2="{PY+PH+6}" stroke="{C["red"]}" stroke-width="1"/>')
    A.append(f'<text x="{sx(f):.0f}" y="{PY+PH+21}" text-anchor="middle" font-family="JetBrains Mono" font-size="12" fill="{C["mut"]}">{int(f*100)}%</text>')
for m in ax["y"]["ticks"]:
    A.append(f'<line x1="{PX-6}" y1="{sy(m):.0f}" x2="{PX}" y2="{sy(m):.0f}" stroke="{C["red"]}" stroke-width="1"/>')
    A.append(f'<text x="{PX-10}" y="{sy(m)+4:.0f}" text-anchor="end" font-family="JetBrains Mono" font-size="12" fill="{C["mut"]}">{m:+.2f}</text>')
A.append(f'<text x="{PX+PW/2:.0f}" y="{PY+PH+44}" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="14" letter-spacing="1" fill="{C["ink"]}">{ax["x"]["label"]}</text>')
A.append(f'<text x="34" y="{PY+PH/2:.0f}" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="14" letter-spacing="1" fill="{C["ink"]}" transform="rotate(-90 34 {PY+PH/2:.0f})">{ax["y"]["label"]}</text>')
# trade-off arrow + labels
A.append(f'<path d="M {sx(0.70):.0f} {sy(0.005):.0f} Q {sx(0.645):.0f} {sy(0.05):.0f} {sx(0.60):.0f} {sy(0.082):.0f}" fill="none" stroke="{C["ink"]}" stroke-width="1.4" opacity="0.8" marker-end="url(#ar)"/>')
A.append(f'<text x="{sx(0.455):.0f}" y="{sy(0.088):.0f}" font-family="Montserrat" font-weight="600" font-size="12.5" fill="{C["ink"]}">more targets = less margin</text>')
A.append(f'<text x="{sx(0.685):.0f}" y="{sy(-0.028):.0f}" font-family="Montserrat" font-weight="700" font-size="13" fill="{C["sage"]}" letter-spacing="1">ROBUST FRONT</text>')
A.append(f'<text x="{sx(0.30):.0f}" y="{sy(0.055):.0f}" font-family="Montserrat" font-weight="700" font-size="13" fill="{C["mut"]}" letter-spacing="1">DOMINATED</text>')
A.append(f'<text x="{sx(0.42):.0f}" y="{sy(-0.052):.0f}" font-family="JetBrains Mono" font-size="11" fill="{C["mut"]}" opacity="0.7">gen 1 &#8230; gen {S["params"]["generations"]}</text>')
# iteration box top-right
pp=S["params"]
A.append(f'<text x="{PX+PW:.0f}" y="{PY-96}" text-anchor="end" font-family="Montserrat" font-weight="800" font-size="15" fill="{C["ink"]}">ROBUST SEARCH</text>')
for i,(k,v) in enumerate([("GEN",f'{pp["generations"]} / {pp["generations"]}'),("POPULATION",pp["population"]),("OBJECTIVES","satisficing + regret"),("PARAMETERS",pp["parameters"])]):
    A.append(f'<text x="{PX+PW:.0f}" y="{PY-76+i*16:.0f}" text-anchor="end" font-family="JetBrains Mono" font-size="11.5" fill="{C["mut"]}">{k}: {v}</text>')
A.append(f'<text x="{PX:.0f}" y="{PY-90}" font-family="Montserrat" font-weight="800" font-size="16" fill="{C["ink"]}">ACCEPTANCE × FUTURES</text>')
A.append(f'<text x="{PX:.0f}" y="{PY-72}" font-family="Spectral" font-style="italic" font-size="13" fill="{C["mut"]}">{S["counts"]["total"]} ordered sequences · {S["counts"]["futures"]} futures each</text>')
# labelled pathways + selected
ST={"dominated":C["ink"],"near":C["gold"],"front":C["sage"],"chosen":C["terra"]}
L=[]
sel=None
for p in S["pathways"]:
    f,m=p["futures"],p["margin"]; x,y=sx(f),sy(m)
    if p["status"] in("front","chosen"):
        L.append(c(f,m,6.4,C["sage"],1,C["ink"],1.3))
    elif p["status"]=="near":
        L.append(c(f,m,5.8,C["gold"],1))
    else:
        L.append(c(f,m,5.2,C["ink"],0.5))
    L.append(f'<text x="{x:.1f}" y="{y-11:.1f}" text-anchor="middle" font-family="Montserrat" font-weight="800" font-size="15" fill="{C["ink"]}">{p["id"]}</text>')
    if p["status"]=="chosen": sel=(f,m,x,y)
f,m,x,y=sel
L.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="none" stroke="{C["terra"]}" stroke-width="2.4"/>')
L.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{PY+PH:.1f}" stroke="{C["terra"]}" stroke-width="1" stroke-dasharray="3 4" opacity="0.8"/>')
L.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{PX:.1f}" y2="{y:.1f}" stroke="{C["terra"]}" stroke-width="1" stroke-dasharray="3 4" opacity="0.8"/>')
L.append(f'<text x="{x+20:.1f}" y="{y-5:.1f}" font-family="Montserrat" font-weight="700" font-size="13" fill="{C["terra"]}">SELECTED · E</text>')
L.append(f'<text x="{x+20:.1f}" y="{y+11:.1f}" font-family="JetBrains Mono" font-size="11" fill="{C["ink"]}">{int(f*100)}% futures · margin {m:+.2f}</text>')

# ---- convergence inset ----
cg=[]
ix,iy,iw,ih=PX+PW-230,PY+PH+70,200,96
cg.append(f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="none" stroke="{C["line"]}" stroke-width="1"/>')
pts=[]
for gx in range(0,201,10):
    v=1-math.exp(-gx/45); 
    pts.append((ix+gx/200*iw, iy+ih-6-v*(ih-16)))
cg.append('<polyline points="'+" ".join(f"{a:.1f},{b:.1f}" for a,b in pts)+f'" fill="none" stroke="{C["ink"]}" stroke-width="1.6"/>')
convx=ix+pp["converge_gen"]/200*iw
cg.append(f'<line x1="{convx:.0f}" y1="{iy}" x2="{convx:.0f}" y2="{iy+ih}" stroke="{C["gold"]}" stroke-width="1" stroke-dasharray="3 3"/>')
cg.append(f'<circle cx="{convx:.0f}" cy="{iy+ih-6-(1-math.exp(-pp["converge_gen"]/45))*(ih-16):.0f}" r="3" fill="{C["gold"]}"/>')
cg.append(f'<text x="{ix}" y="{iy-7}" font-family="Montserrat" font-weight="700" font-size="11" fill="{C["ink"]}">HYPERVOLUME CONVERGENCE &#183; gen ~{pp["converge_gen"]}</text>')
cg.append(f'<text x="{ix}" y="{iy+ih+15}" font-family="JetBrains Mono" font-size="10" fill="{C["mut"]}">hypervolume vs generation \u00b7 mean of {pp.get("seeds",10)} seeds</text>')

# params box (left of convergence)
pbx,pby=PX-8,PY+PH+58
pbox=[f'<rect x="{pbx}" y="{pby}" width="330" height="128" fill="{C["dark"]}" stroke="{C["line"]}" rx="5"/>']
plines=[("ALGORITHM",pp["algorithm"]),("POPULATION / GEN",f'{pp["population"]} / {pp["generations"]}'),
        ("OBJECTIVES",pp["objectives"]),("CONSTRAINTS","acceptance ≥ λ every year,"),("","revenue ≥ debt, accessibility floor")]
for i,(k,v) in enumerate(plines):
    kk=f'<tspan fill="{C["gold"]}">{k}: </tspan>' if k else ""
    pbox.append(f'<text x="{pbx+14}" y="{pby+22+i*18:.0f}" font-family="JetBrains Mono" font-size="11.5" fill="{C["ink"]}">{kk}{v}</text>')

svg=f'''<svg viewBox="0 0 980 812" width="100%" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{C["ink"]}"/></marker></defs>
{''.join(E)}{''.join(A)}{''.join(L)}{''.join(cg)}{''.join(pbox)}
</svg>'''

# pathway cards (isometric instrument stacks)
def isopath(cx,cy,n,col):
    # n stacked blocks as simple iso prisms rising
    out=""; bw=16; bh=9
    for i in range(n):
        ox=cx+i*14; oy=cy-i*5
        # top rhombus
        out+=f'<polygon points="{ox},{oy} {ox+bw},{oy-bh} {ox+2*bw},{oy} {ox+bw},{oy+bh}" fill="none" stroke="{col}" stroke-width="1.4"/>'
        out+=f'<polygon points="{ox},{oy} {ox},{oy+20} {ox+bw},{oy+bh+20} {ox+bw},{oy+bh}" fill="{col}" opacity="0.18" stroke="{col}" stroke-width="1.1"/>'
        out+=f'<polygon points="{ox+bw},{oy+bh} {ox+bw},{oy+bh+20} {ox+2*bw},{oy+20} {ox+2*bw},{oy}" fill="{col}" opacity="0.30" stroke="{col}" stroke-width="1.1"/>'
    return out
cards=""
inm=S["instrument_names"]
for p in S["pathways"]:
    col=ST[p["status"]]; chosen=p["status"]=="chosen"
    seq=" &#8594; ".join(inm[o] for o in p["order"])
    iso=f'<svg viewBox="0 0 120 80" width="120" height="80" xmlns="http://www.w3.org/2000/svg">{isopath(18,46,len(p["order"]),col)}</svg>'
    cls="rfcard chosen" if chosen else "rfcard"
    tag='<div class="rtag">chosen &#183; widest λ it survives</div>' if chosen else ""
    cards+=f'''<div class="{cls}"><div class="rk" style="color:{col if chosen else C["ink"]}">{p["id"]}</div>{iso}
      <div class="rseq">{seq}</div><div class="rnum">{int(p["futures"]*100)}% futures &#183; {p["margin"]:+.2f}</div>{tag}</div>'''

html=f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Spectral:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
body{{margin:0;background:#140a0e;font-family:Spectral,serif}}
.rf{{width:900px;margin:0 auto;background:{C["bg"]};padding:34px 40px 30px;color:{C["ink"]}}}
.rflabel{{display:inline-block;font-family:Montserrat;font-weight:700;font-size:11px;letter-spacing:1.6px;color:#140a0e;background:{C["gold"]};padding:3px 10px;border-radius:3px;text-transform:uppercase}}
.rfcards{{display:grid;grid-template-columns:repeat(5,1fr);gap:11px;margin-top:16px}}
.rfcard{{background:{C["dark"]};border:1px solid {C["line"]};border-radius:6px;padding:10px 10px 12px;text-align:center}}
.rfcard.chosen{{border-color:{C["terra"]};box-shadow:0 0 0 1px {C["terra"]} inset}}
.rk{{font-family:Montserrat;font-weight:900;font-size:22px;text-align:left}}
.rseq{{font-family:JetBrains Mono;font-size:9.5px;color:{C["mut"]};margin-top:4px}}
.rnum{{font-family:JetBrains Mono;font-size:11px;color:{C["gold"]};margin-top:5px}}
.rtag{{font-family:Spectral;font-style:italic;font-size:10.5px;color:{C["terra"]};margin-top:5px}}
.rftitle{{font-family:Montserrat;font-weight:900;font-size:34px;margin:18px 0 4px;letter-spacing:-.5px}}
.rfsub{{font-family:Spectral;font-style:italic;font-size:14px;color:#c9b8a8;max-width:80ch}}
.rftier{{font-family:JetBrains Mono;font-size:10px;color:#8f7a86;border:1px solid {C["line"]};border-radius:3px;padding:2px 7px;display:inline-block;margin-top:10px}}
.rflegend{{display:flex;gap:18px;flex-wrap:wrap;font-family:Montserrat;font-size:11px;color:{C["mut"]};margin:14px 0 4px;align-items:center}}
.rflegend i{{width:12px;height:12px;border-radius:50%;display:inline-block;margin-right:6px;vertical-align:-2px}}
</style></head><body><div class="rf">
<span class="rflabel">Robustness &#183; regret &#183; receipts</span>
<div class="rflegend">
<span><i style="background:{C["sage"]}"></i>robust (on the front)</span>
<span><i style="background:{C["gold"]}"></i>near-optimal</span>
<span><i style="background:{C["ink"]};opacity:.5"></i>dominated</span>
<span><i style="background:{C["terra"]}"></i>chosen pathway</span>
</div>
{svg}
<div class="rfcards">{cards}</div>
<div class="rftitle">{S["title"]}</div>
<div class="rfsub">{S["subtitle"]}</div>
<div class="rftier">{S["tier"]}</div>
</div></body></html>'''
open("robustfront.html","w").write(html)
print("built robustfront.html")
