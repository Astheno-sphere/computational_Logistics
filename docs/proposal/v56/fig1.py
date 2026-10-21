import math
# ---------- Fig 1a: Kristiansund exposure, hex field + 3-moment timeline ----------
def hexpts(cx,cy,r):
    p=[]
    for i in range(6):
        a=math.pi/180*(60*i-30)
        p.append(f"{cx+r*math.cos(a):.1f},{cy+r*math.sin(a):.1f}")
    return " ".join(p)

# two lobes: Nordlandet (left, bridge-dependent, high exposure) + Kirkelandet core (right),
# a southern tail (tunnel-served, free alt). axial hex layout.
R=15.5; dx=R*math.sqrt(3); dy=R*1.5
# define cluster membership by hand-placed centres (col,row) -> class
# class: 2 high (pays both), 1 partial, 0 free-alt
cells=[]
def add(col,row,cls):
    x=60+col*dx+(row%2)*dx/2
    y=46+row*dy
    cells.append((x,y,cls))
# Nordlandet lobe (left, high) - a compact cluster
for (c,r_) in [(0,1),(1,1),(0,2),(1,2),(2,2),(0,3),(1,3),(2,3),(1,4),(2,4)]:
    add(c,r_,2)
# Kirkelandet core (middle-right, partial->high gradient)
for (c,r_) in [(4,0),(5,0),(4,1),(5,1),(6,1),(5,2),(6,2),(7,2),(4,2),(6,3),(7,3),(5,3),(7,1)]:
    add(c,r_,1)
# a few core-high (town centre)
for (c,r_) in [(5,1),(6,2)]:
    pass
# southern tail (tunnel-served, free alternative)
for (c,r_) in [(3,5),(4,5),(5,5),(4,6),(5,6),(6,5)]:
    add(c,r_,0)
EXP={2:"#D4A530",1:"#9c6a2e",0:"#5f4336"}
hexes=[]
for x,y,cls in cells:
    stroke="#7CBAC4" if cls==0 else "#2E151C"
    sw=1.6 if cls==0 else 1
    hexes.append(f'<polygon points="{hexpts(x,y,R)}" fill="{EXP[cls]}" stroke="{stroke}" stroke-width="{sw}" opacity="0.92"/>')
# toll + tunnel markers
mk=[]
def dot(x,y,lab,sub,col="#E8DFD0"):
    return (f'<circle cx="{x}" cy="{y}" r="5.5" fill="#2E151C" stroke="{col}" stroke-width="2"/>'
            f'<text x="{x+10}" y="{y-2}" font-family="Montserrat" font-weight="700" font-size="11" fill="#E8DFD0">{lab}</text>'
            f'<text x="{x+10}" y="{y+11}" font-family="JetBrains Mono" font-size="9" fill="#b89a86">{sub}</text>')
# bridge between lobes ~ (between left cluster and core)
mk.append(dot(150,120,"Nordsundbrua","rv70 · pays"))
mk.append(dot(300,86,"Omsundbrua","second station"))
mk.append(dot(150,250,"Atlanterhavstunnelen","toll-free · fv64","#7CBAC4"))
# connector line (free route)
mk.append('<path d="M150 250 Q 110 200 120 150" fill="none" stroke="#7CBAC4" stroke-width="1.6" stroke-dasharray="4 4" opacity="0.8"/>')

fig1a=f'''<svg viewBox="0 0 470 300" width="100%" xmlns="http://www.w3.org/2000/svg">
{''.join(hexes)}
{''.join(mk)}
<text x="18" y="20" font-family="Montserrat" font-weight="700" font-size="11" letter-spacing="1.5" fill="#E8DFD0">KRISTIANSUND · TOLL EXPOSURE</text>
</svg>'''

# exposure legend
leg1a='''<div class="exlegend">
<span><i class="sw" style="background:#D4A530"></i>pays both ways</span>
<span><i class="sw" style="background:#9c6a2e"></i>partial</span>
<span><i class="sw" style="background:#5f4336;outline:1.5px solid #7CBAC4;outline-offset:-2px"></i>free alternative (tunnel)</span>
<span class="tier">REAL · OSM graph</span>
</div>'''

# 3-moment timeline
mom=[("2026","40%","23.94"),("2035","80%","20.67"),("2050","99%","19.12")]
cells_t="".join(
 f'<div class="mcell"><div class="myr">{y}</div>'
 f'<div class="mbarwrap"><div class="mbar" style="width:{int(float(ev[:-1]))}%"></div></div>'
 f'<div class="mev">{ev} electric</div>'
 f'<div class="mrev">NOK {rev}<span>/crossing</span></div></div>'
 for y,ev,rev in mom)
timeline=f'''<div class="timeline">
<div class="tlhead">THE SAME PLACE, THREE MOMENTS<span class="tier">electric share PROTOTYPE · revenue computed from tariff</span></div>
<div class="moments">{cells_t}</div></div>'''

# ---------- Fig 1b: what a crossing earns (calculator readout) ----------
fig1b='''<div class="calc">
<div class="qline">&gt; what one crossing earns, by fleet</div>
<div class="crow"><span class="cl">standard car</span><span class="cv">NOK 34.00</span></div>
<div class="crow"><span class="cl">with tag</span><span class="cv">NOK 27.20</span></div>
<div class="crow hl"><span class="cl">zero-emission + tag</span><span class="cv">NOK 19.04</span></div>
<div class="cdiv"></div>
<div class="crow"><span class="cl">each electric crossing earns</span><span class="cv gold">NOK 8.16 less &nbsp;·&nbsp; &minus;30%</span></div>
<div class="crow"><span class="cl">at today&rsquo;s 40% electric</span><span class="cv">&minus;12% vs an all-fossil fleet</span></div>
<div class="crow"><span class="cl">at an all-electric fleet</span><span class="cv">&minus;30%, debt unchanged</span></div>
<div class="cdiv"></div>
<div class="crow res"><span class="cl">the base erodes, the debt holds</span><span class="cv gold">~NOK 78 bn owed</span></div>
<div class="ctier">REAL · Vegamot tariff [vegamot]</div>
</div>'''

open("fig1_parts.py","w").write("FIG1A=%r\nLEG1A=%r\nTIMELINE=%r\nFIG1B=%r\n"%(fig1a,leg1a,timeline,fig1b))
print("fig1 parts built")
