import math, random
random.seed(11)
W,H=720,74   # strip plot area
# ---- one schematic street network, defined once ----
arterials=[]
for k,base in enumerate([18,38,58]):
    pts=[]
    for i in range(0,W+1,30):
        y=base+10*math.sin(i/90+k*1.4)+random.uniform(-2,2)
        pts.append((i,y))
    d="M "+" L ".join(f"{x:.0f} {y:.1f}" for x,y in pts)
    arterials.append(d)
# cross streets
cross=[]
for x in range(60,W,55):
    y0=random.uniform(6,20); y1=random.uniform(54,70)
    cross.append(f"M {x} {y0:.0f} L {x+random.uniform(-10,10):.0f} {y1:.0f}")
# minor grid patch (town centre) middle
grid=[]
for gx in range(300,470,22):
    grid.append(f"M {gx} 20 L {gx} 60")
for gy in range(20,62,13):
    grid.append(f"M 300 {gy} L 460 {gy}")
# intersection nodes
nodes=[(x,30+8*math.sin(x/90)) for x in range(70,W,70)]

def net(stroke,sw,op):
    s="".join(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>' for d in arterials)
    s+="".join(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw*0.6:.2f}" opacity="{op*0.7}"/>' for d in cross)
    s+="".join(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw*0.5:.2f}" opacity="{op*0.6}"/>' for d in grid)
    return s

strips=[
 # key, name, tier, tool, article, tiercolor
 ("network","NETWORK","REAL","OSMnx · NetworkX","the graph","#9DB886"),
 ("choice","CHOICE","TO ESTIMATE · A1","Biogeme","who chooses what","#D4835C"),
 ("accept","ACCEPTANCE","TO ESTIMATE · A2","EMA Workbench","each home remembers","#D4835C"),
 ("fleet","FLEET + EMISSIONS","PROTOTYPE","register · WTW","turns over slowly","#D4A530"),
 ("revenue","REVENUE","PROTOTYPE","tariff ÷ debt","due on a schedule","#D4A530"),
 ("freight","FREIGHT","NGM","national freight model","road vs sea","#7CBAC4"),
]

def overlay(key):
    o=""
    if key=="network":
        o=net("#E8DFD0",1.5,0.9)
        o+="".join(f'<circle cx="{x}" cy="{y:.0f}" r="2.2" fill="#E8DFD0" opacity="0.8"/>' for x,y in nodes)
    elif key=="choice":
        o=net("#E8DFD0",1,0.28)
        # choices at nodes = outlined dots, dashed ring = to estimate
        for x,y in nodes:
            o+=f'<circle cx="{x}" cy="{y:.0f}" r="5" fill="none" stroke="#D4835C" stroke-width="1.5" stroke-dasharray="3 2"/>'
        o+='<text x="8" y="70" font-family="JetBrains Mono" font-size="8.5" fill="#8f7a86">latent choice + acceptance, not yet estimated</text>'
    elif key=="accept":
        o=net("#E8DFD0",1,0.28)
        # faint zone polys with hatch
        zones=[(90,"M40 8 L180 10 L170 66 L36 60 Z"),(260,"M210 8 L400 12 L395 66 L205 64 Z"),(470,"M430 10 L690 8 L688 66 L440 66 Z")]
        fills=[0.10,0.20,0.07]
        for (cx,d),f in zip(zones,fills):
            o+=f'<path d="{d}" fill="#D4835C" opacity="{f}" stroke="#D4835C" stroke-width="0.8" stroke-dasharray="4 3"/>'
    elif key=="fleet":
        # gradient fossil->electric along x
        o=f'<defs><linearGradient id="fl" x1="0" x2="1"><stop offset="0" stop-color="#8a5a3a"/><stop offset="1" stop-color="#D4A530"/></linearGradient></defs>'
        o+="".join(f'<path d="{d}" fill="none" stroke="url(#fl)" stroke-width="2.2" opacity="0.95"/>' for d in arterials)
        o+=net("#E8DFD0",1,0.18)
        o+='<text x="8" y="70" font-family="JetBrains Mono" font-size="8.5" fill="#8f7a86">40% → 99% electric, 2026→2050</text>'
    elif key=="revenue":
        o=net("#E8DFD0",1,0.3)
        for x,lab in [(150,"A"),(470,"B")]:
            o+=f'<circle cx="{x}" cy="34" r="6" fill="#2E151C" stroke="#D4A530" stroke-width="2"/><text x="{x-3}" y="38" font-family="Montserrat" font-weight="700" font-size="9" fill="#D4A530">{lab}</text>'
        # flow arrows
        o+='<path d="M 160 34 L 300 34" stroke="#D4A530" stroke-width="1.4" opacity="0.7" marker-end="url(#a2)"/>'
        o+='<text x="520" y="38" font-family="JetBrains Mono" font-size="8.5" fill="#8f7a86">revenue ÷ debt service</text>'
    elif key=="freight":
        o=net("#E8DFD0",1,0.28)
        o+='<path d="M 120 58 C 300 40, 480 30, 700 18" fill="none" stroke="#7CBAC4" stroke-width="2.6" opacity="0.95"/>'
        o+='<text x="520" y="14" font-family="JetBrains Mono" font-size="8.5" fill="#7CBAC4">road → coastal short-sea</text>'
    return o

rows=""
for key,name,tier,tool,art,tc in strips:
    rows+=f'''<div class="lstrip">
      <div class="llabel">
        <div class="lname">{name}</div>
        <div class="lmeta"><span class="lchip" style="border-color:{tc};color:{tc}">{tier}</span></div>
        <div class="ltool">{tool}</div>
        <div class="lrole">{art}</div>
      </div>
      <div class="lband"><svg viewBox="0 0 {W} {H}" width="100%" height="{H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <defs><marker id="a2" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="#D4A530"/></marker></defs>
      {overlay(key)}</svg></div>
    </div>'''
FIG2=f'<div class="lstack">{rows}</div>'
open("fig2_parts.py","w").write("FIG2=%r\n"%FIG2)
print("fig2 built")
