import json
C={"ink":"#E8DFD0","mut":"#b89a86","gold":"#D4A530","sage":"#9DB886","terra":"#D4835C","red":"#C45545","teal":"#7CBAC4","line":"#5a3a40"}
W,H=760,300
def fx(r): return 70+r/3.0*300
def fy(sh): return 30+(1.0-sh)*(H-150)
road=[(0,0.92),(0.5,0.88),(1.0,0.80),(1.5,0.66),(2.0,0.46),(2.5,0.30),(3.0,0.22)]
sea=[(0,0.08),(0.5,0.12),(1.0,0.20),(1.5,0.34),(2.0,0.54),(2.5,0.70),(3.0,0.78)]
thr=1.85
ff=[]
ff.append('<rect x="%d" y="30" width="%d" height="%d" fill="%s" opacity="0.08"/>'%(fx(thr),fx(3)-fx(thr),H-120,C["sage"]))
ff.append('<line x1="%d" y1="26" x2="%d" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="4 3"/>'%(fx(thr),fx(thr),H-90,C["sage"]))
ff.append('<text x="%d" y="44" font-family="Montserrat" font-weight="700" font-size="10" fill="%s">modal-shift window</text>'%(fx(thr)+6,C["sage"]))
for pts,col,lab in [(road,C["gold"],"road"),(sea,C["teal"],"coastal short-sea")]:
    d="M "+" L ".join("%d %d"%(fx(r),fy(sh)) for r,sh in pts)
    ff.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.4"/>'%(d,col))
    lr,lsh=pts[-1]; ff.append('<text x="%d" y="%d" text-anchor="end" font-family="Montserrat" font-weight="600" font-size="11" fill="%s">%s</text>'%(fx(lr)-4,fy(lsh)+4,col,lab))
for r in [0,1,2,3]:
    ff.append('<text x="%d" y="%d" text-anchor="middle" font-family="JetBrains Mono" font-size="10" fill="%s">%d</text>'%(fx(r),H-72,C["mut"],r))
ff.append('<text x="%d" y="%d" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="11" fill="%s">DISTANCE CHARGE (NOK/km)</text>'%(fx(1.5),H-54,C["ink"]))
ff.append('<text x="34" y="%d" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="11" fill="%s" transform="rotate(-90 34 %d)">MODE SHARE</text>'%(fy(0.5),C["ink"],fy(0.5)))
ff.append('<text x="70" y="20" font-family="Montserrat" font-weight="700" font-size="11" fill="%s">H3 · carrier mode choice under a distance charge</text>'%C["ink"])
LEFT='<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg">%s</svg>'%(W,H,"".join(ff))

W2,H2=760,150
def tx(yr): return 60+(yr-2026)/24.0*(W2-110)
sg=['<line x1="60" y1="75" x2="%d" y2="75" stroke="%s" stroke-width="1.5"/>'%(W2-40,C["line"])]
for yr in [2026,2035,2050]:
    sg.append('<text x="%d" y="100" text-anchor="middle" font-family="JetBrains Mono" font-size="10" fill="%s">%d</text>'%(tx(yr),C["mut"],yr))
for yr,lab,col,sub in [(2032,"FREIGHT signpost",C["teal"],"fires first — slow heavy fleet"),(2037,"PASSENGER signpost",C["gold"],"fires later")]:
    sg.append('<circle cx="%d" cy="75" r="7" fill="#2b161c" stroke="%s" stroke-width="2.5"/>'%(tx(yr),col))
    sg.append('<line x1="%d" y1="68" x2="%d" y2="40" stroke="%s" stroke-width="1"/>'%(tx(yr),tx(yr),col))
    sg.append('<text x="%d" y="34" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="11" fill="%s">%s · %d</text>'%(tx(yr),col,lab,yr))
    sg.append('<text x="%d" y="122" text-anchor="middle" font-family="Spectral" font-style="italic" font-size="10.5" fill="%s">%s</text>'%(tx(yr),C["mut"],sub))
sg.append('<path d="M %d 75 L %d 75" stroke="%s" stroke-width="2" marker-end="url(#fa)"/>'%(tx(2032)+9,tx(2037)-9,C["red"]))
sg.append('<text x="%d" y="64" text-anchor="middle" font-family="Montserrat" font-weight="600" font-size="10" fill="%s">the window between is where freight locks in</text>'%((tx(2032)+tx(2037))/2,C["red"]))
RIGHT='<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg"><defs><marker id="fa" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="%s"/></marker></defs>%s</svg>'%(W2,H2,C["red"],"".join(sg))

note='<div class="f5bnote" style="margin-top:4px">Carriers shift to coastal short-sea once the distance charge passes a threshold; the heavy fleet turns over slowly, so the freight signpost must fire before the passenger one. Load factors and empty running come from NGM. <span class="tier">PROTOTYPE · estimated from the carrier block in A1</span></div>'
FIGFREIGHT='<div class="twocol" style="gap:16px"><div>'+LEFT+'</div><div>'+RIGHT+note+'</div></div>'
json.dump({"FIGFREIGHT":FIGFREIGHT}, open("freight.json","w"))
print("freight.json built")
