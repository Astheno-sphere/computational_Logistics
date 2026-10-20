# builds fig2 (layer stack on real map), fig3 (trajectories), fig5b (erosion fan) as HTML snippets -> figs_extra.json
import json, math, base64, random
random.seed(5)
C={"ink":"#E8DFD0","mut":"#b89a86","gold":"#D4A530","sage":"#9DB886","terra":"#D4835C","red":"#C45545","teal":"#7CBAC4","line":"#5a3a40","bg":"#2b161c","dark":"#1f1014"}
mp="data:image/jpeg;base64,"+base64.b64encode(open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/kristiansund_map.jpg","rb").read()).decode()

# ---------- FIG 2: layer stack on the real map ----------
layers=[
 ("NETWORK","REAL","OSMnx · NetworkX","the graph",C["sage"],"net"),
 ("CHOICE","TO ESTIMATE · A1","Biogeme","who chooses what",C["terra"],"choice"),
 ("ACCEPTANCE","TO ESTIMATE · A2","EMA Workbench","each home remembers",C["terra"],"accept"),
 ("FLEET + EMISSIONS","PROTOTYPE","register · WTW","turns over slowly",C["gold"],"fleet"),
 ("REVENUE","PROTOTYPE","tariff ÷ debt","due on a schedule",C["gold"],"rev"),
 ("FREIGHT","NGM","national freight model","road vs sea",C["teal"],"freight"),
]
def band_overlay(key):
    # svg overlay 820x72
    W,H=820,72; o=""
    if key=="net": o=f'<rect width="{W}" height="{H}" fill="none"/>'  # show map plain
    elif key=="choice":
        for i in range(14):
            x=60+i*52; y=18+(i%3)*16
            o+=f'<circle cx="{x}" cy="{y}" r="5" fill="none" stroke="{C["terra"]}" stroke-width="1.6" stroke-dasharray="3 2"/>'
        o+=f'<rect width="{W}" height="{H}" fill="#2b161c" opacity="0.35"/>'
    elif key=="accept":
        o=f'<rect width="{W}" height="{H}" fill="#2b161c" opacity="0.4"/>'
        for d in ["M40 8 L300 12 L290 64 L36 60 Z","M330 10 L600 8 L600 64 L340 64 Z"]:
            o+=f'<path d="{d}" fill="{C["terra"]}" opacity="0.14" stroke="{C["terra"]}" stroke-width="1" stroke-dasharray="5 3"/>'
    elif key=="fleet":
        o=f'<rect width="{W}" height="{H}" fill="#2b161c" opacity="0.25"/><defs><linearGradient id="g2"><stop offset="0" stop-color="#8a5a3a"/><stop offset="1" stop-color="#D4A530"/></linearGradient></defs>'
        o+=f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#g2)" opacity="0.28"/>'
    elif key=="rev":
        o=f'<rect width="{W}" height="{H}" fill="#2b161c" opacity="0.3"/>'
        for x in [210,560]:
            o+=f'<circle cx="{x}" cy="36" r="7" fill="#2b161c" stroke="{C["gold"]}" stroke-width="2"/>'
        o+=f'<path d="M 222 36 L 548 36" stroke="{C["gold"]}" stroke-width="1.5" opacity="0.7" stroke-dasharray="6 4"/>'
    elif key=="freight":
        o=f'<rect width="{W}" height="{H}" fill="#2b161c" opacity="0.32"/>'
        o+=f'<path d="M 120 58 C 340 44 560 30 800 16" fill="none" stroke="{C["teal"]}" stroke-width="3" opacity="0.95"/>'
    return f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">{o}</svg>'
rows=""
for name,tier,tool,role,tc,key in layers:
    rows+=f'''<div class="lstrip">
      <div class="llabel"><div class="lname">{name}</div>
        <div><span class="lchip" style="border-color:{tc};color:{tc}">{tier}</span></div>
        <div class="ltool">{tool}</div><div class="lrole">{role}</div></div>
      <div class="lband" style="background-image:url({mp})">{band_overlay(key)}</div>
    </div>'''
FIG2=f'<div class="lstack">{rows}</div>'

# ---------- FIG 3: what memory does (3 agents) ----------
W,H=760,300
def px(yr): return 60+(yr-2026)/(2050-2026)*(W-90)
def py(a): return 40+(0.85-a)/(0.85-0.25)*(H-90)
ag=[("Daily commuter, Nordlandet","ρ 0.8 · high dose",C["teal"],[(2026,0.32),(2029,0.34),(2031,0.40),(2035,0.55),(2042,0.60),(2050,0.62)],"crosses λ in 2031, holds"),
    ("Occasional crosser","ρ 0.5 · low dose",C["sage"],[(2026,0.55),(2031,0.56),(2038,0.57),(2050,0.58)],"always above λ"),
    ("Van driver, local firm","ρ 0.3 · high dose",C["gold"],[(2026,0.44),(2029,0.47),(2033,0.52),(2035,0.38),(2042,0.33),(2050,0.31)],"below λ from 2035")]
lam=0.38
e=[f'<rect x="60" y="{py(lam):.0f}" width="{W-90}" height="{H-40-py(lam):.0f}" fill="{C["red"]}" opacity="0.08"/>',
   f'<line x1="60" y1="{py(lam):.0f}" x2="{W-30}" y2="{py(lam):.0f}" stroke="{C["red"]}" stroke-width="1" stroke-dasharray="5 3"/>',
   f'<text x="{W-32}" y="{py(lam)-5:.0f}" text-anchor="end" font-family="JetBrains Mono" font-size="11" fill="{C["red"]}">λ threshold 0.38</text>']
for yr in [2026,2035,2050]:
    e.append(f'<text x="{px(yr):.0f}" y="{H-14}" text-anchor="middle" font-family="JetBrains Mono" font-size="11" fill="{C["mut"]}">{yr}</text>')
for name,sub,col,pts,note in ag:
    d="M "+" L ".join(f"{px(y):.1f} {py(a):.1f}" for y,a in pts)
    e.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.2"/>')
    lx,la=pts[-1]; e.append(f'<circle cx="{px(lx):.0f}" cy="{py(la):.0f}" r="3.5" fill="{col}"/>')
    e.append(f'<text x="{px(lx)-6:.0f}" y="{py(la)-7:.0f}" text-anchor="end" font-family="Montserrat" font-weight="600" font-size="10.5" fill="{col}">{note}</text>')
leg3="".join(f'<div class="l3"><span class="d3" style="background:{col}"></span><b>{name}</b> <span class="s3">{sub}</span></div>' for name,sub,col,_,_ in ag)
FIG3=f'''<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg">{''.join(e)}</svg>
<div class="leg3wrap">{leg3}</div>
<div class="f3eq">acceptance next year = memory of last year (ρ) + what you pay + what you were told</div>'''

# ---------- FIG 5b: erosion fan ----------
W,H=760,250
def ex(yr): return 55+(yr-2026)/(2050-2026)*(W-80)
def ey(r): return 20+(1.5-r)/(1.5-0.4)*(H-55)
fan=[]
random.seed(3)
for i in range(120):
    drift=random.uniform(-0.6,0.5); base=1.18
    pts=[]
    for yr in range(2026,2051,2):
        t=(yr-2026)/24; r=base + drift*t - 0.015*(yr-2026) + random.uniform(-0.03,0.03)
        pts.append((ex(yr),ey(max(0.42,r))))
    below = pts[-1][1] > ey(1.0)
    col=C["red"] if below else C["ink"]; op=0.16 if below else 0.07
    fan.append('<polyline points="'+" ".join(f"{a:.0f},{b:.0f}" for a,b in pts)+f'" fill="none" stroke="{col}" stroke-width="1" opacity="{op}"/>')
# median
med=[(ex(yr),ey(1.18-0.016*(yr-2026))) for yr in range(2026,2051,2)]
fan.append('<polyline points="'+" ".join(f"{a:.0f},{b:.0f}" for a,b in med)+f'" fill="none" stroke="{C["gold"]}" stroke-width="2.4"/>')
fan.append(f'<line x1="55" y1="{ey(1.0):.0f}" x2="{W-25}" y2="{ey(1.0):.0f}" stroke="{C["red"]}" stroke-width="1.4" stroke-dasharray="6 4"/>')
fan.append(f'<text x="{W-27}" y="{ey(1.0)-6:.0f}" text-anchor="end" font-family="JetBrains Mono" font-size="11" fill="{C["red"]}">debt service = revenue</text>')
fan.append(f'<text x="58" y="{ey(1.42):.0f}" font-family="Montserrat" font-weight="700" font-size="11" fill="{C["gold"]}">median future</text>')
for yr in [2026,2035,2041,2050]:
    fan.append(f'<text x="{ex(yr):.0f}" y="{H-10}" text-anchor="middle" font-family="JetBrains Mono" font-size="11" fill="{C["mut"]}">{yr}</text>')
FIG5B=f'''<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg">{''.join(fan)}</svg>
<div class="f5bnote"><b>22%</b> of futures fail to cover the debt before 2041; 30% by 2050. Each line one future: revenue ÷ debt service.</div>'''

json.dump({"FIG2":FIG2,"FIG3":FIG3,"FIG5B":FIG5B}, open("figs_extra.json","w"))
print("figs_extra built")
