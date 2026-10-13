// Plates for the A3 proposal. Colour carries meaning: electric green, fossil grey, vans blue, opinion vermilion,
// money gold, futures lavender. Charcoal ground, cream line, Inter type.
const C3 = {g:"#1d1b19", cream:"#E9E1D0", dim:"#8E877D", faint:"rgba(233,225,208,.16)", red:"#D2412B",
  ev:"#7FB89A", fos:"#8E877D", van:"#6E9CC8", gold:"#D4A530", fut:"#B7A4D8", body:"#CFC7B8"};
const SVGNS = "http://www.w3.org/2000/svg";
function E(p, tag, a, txt){const e=document.createElementNS(SVGNS,tag);for(const k in a)e.setAttribute(k,a[k]);if(txt!==undefined)e.textContent=txt;p.appendChild(e);return e}
function T(p, x, y, s, o={}){return E(p,"text",Object.assign({x,y,fill:C3.cream,"font-size":14,"font-family":"Inter,sans-serif",stroke:C3.g,"stroke-width":4,"paint-order":"stroke","stroke-linejoin":"round"},o),s)}
function isoF(ox, oy, k=1){return (u,v,z=0)=>[ox+(u-v)*0.866*k, oy+(u+v)*0.5*k-z]}
function P(iso, pts){return pts.map(q=>iso(...q).map(n=>n.toFixed(1)).join(",")).join(" ")}
function box(s, iso, u, v, z, a, b, h, top, side, front, sw=0.9){
  E(s,"polygon",{points:P(iso,[[u+a,v,z],[u+a,v+b,z],[u+a,v+b,z+h],[u+a,v,z+h]]),fill:side,stroke:C3.cream,"stroke-width":sw});
  E(s,"polygon",{points:P(iso,[[u,v+b,z],[u+a,v+b,z],[u+a,v+b,z+h],[u,v+b,z+h]]),fill:front,stroke:C3.cream,"stroke-width":sw});
  E(s,"polygon",{points:P(iso,[[u,v,z+h],[u+a,v,z+h],[u+a,v+b,z+h],[u,v+b,z+h]]),fill:top,stroke:C3.cream,"stroke-width":sw});
}
function shade(hex, f){const n=parseInt(hex.slice(1),16),r=(n>>16)&255,g=(n>>8)&255,b=n&255;return `rgb(${Math.round(r*f)},${Math.round(g*f)},${Math.round(b*f)})`}

// H1: the toll bridge in isometric, and revenue per passing against electric share
(function(){const s=document.getElementById("h1");if(!s)return;
  const iso=isoF(110,150,0.95);
  // water
  for(let i=0;i<44;i++){const y=160+i*6.2;E(s,"line",{x1:0,y1:y,x2:640,y2:y,stroke:C3.cream,"stroke-opacity":0.10,"stroke-width":0.7});}
  // land at both ends
  E(s,"polygon",{points:P(iso,[[-60,-60,0],[40,-60,0],[40,160,0],[-60,160,0]]),fill:"#24211e",stroke:C3.cream,"stroke-width":0.8});
  E(s,"polygon",{points:P(iso,[[440,-60,0],[560,-60,0],[560,160,0],[440,160,0]]),fill:"#24211e",stroke:C3.cream,"stroke-width":0.8});
  // houses on land
  const house=(u,v,acc)=>{box(s,iso,u,v,0,26,22,20,"#24211e","#1d1b19","#24211e");
    E(s,"polygon",{points:P(iso,[[u,v+22,20],[u+26,v+22,20],[u+26,v+11,31],[u,v+11,31]]),fill:acc?C3.red:"#24211e",stroke:acc?C3.red:C3.cream,"stroke-width":0.9});
    E(s,"polygon",{points:P(iso,[[u+26,v,20],[u+26,v+22,20],[u+26,v+11,31]]),fill:"#1d1b19",stroke:C3.cream,"stroke-width":0.9});};
  [[-50,-50,0],[-50,-12,0],[-50,100,1],[460,-50,0],[500,-14,0],[470,104,0]].forEach(([u,v,a])=>house(u,v,a));
  // piers and deck
  [90,190,290,390].forEach(u=>{box(s,iso,u,20,0,10,40,34,"#24211e","#1d1b19","#24211e",0.8);});
  box(s,iso,40,0,34,400,80,7,"#2a2724","#1d1b19","#24211e",1.1);
  // lane line
  E(s,"polyline",{points:P(iso,[[40,40,41.5],[440,40,41.5]]),fill:"none",stroke:C3.cream,"stroke-width":0.8,"stroke-dasharray":"7 6","stroke-opacity":0.6});
  // vehicles on the deck: electric green, fossil grey, one van
  const car=(u,v,fill,len=24,h=9)=>{box(s,iso,u,v,41,len,13,h,fill,shade(fill.startsWith("#")?fill:"#888888",0.62),shade(fill.startsWith("#")?fill:"#888888",0.8),0.7);};
  [[60,8,C3.ev],[110,8,C3.fos],[165,8,C3.ev],[220,8,C3.fos],[340,8,C3.ev],[392,8,C3.fos],
   [70,54,C3.fos],[128,54,C3.ev],[250,54,C3.fos],[310,54,C3.ev],[370,54,C3.fos]].forEach(([u,v,f])=>car(u,v,f));
  box(s,iso,180,52,41,34,17,16,C3.van,shade(C3.van,0.62),shade(C3.van,0.8),0.8);
  // gantry at u=290
  [[-4],[84]].forEach(([v])=>{const a=iso(290,v,41),b=iso(290,v,41+64);E(s,"line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:C3.cream,"stroke-width":2});});
  E(s,"polygon",{points:P(iso,[[286,-4,103],[294,-4,103],[294,84,103],[286,84,103]]),fill:C3.red,stroke:C3.red,"stroke-width":1});
  E(s,"polygon",{points:P(iso,[[286,84,103],[294,84,103],[294,84,96],[286,84,96]]),fill:shade("#D2412B",0.7),stroke:"none"});
  // people: one reading the charge on the far shore, two waiting on the near shore
  const person=(u,v,h=30)=>{const [x,y]=iso(u,v,0);E(s,"circle",{cx:x,cy:y-h,r:3.4,fill:C3.g,stroke:C3.cream,"stroke-width":1.1});
    E(s,"path",{d:`M${x} ${y-h+4} L${x} ${y-12} M${x} ${y-12} L${x-4} ${y} M${x} ${y-12} L${x+4} ${y} M${x} ${y-h+7} L${x-5} ${y-h+15} M${x} ${y-h+7} L${x+5} ${y-h+15}`,fill:"none",stroke:C3.cream,"stroke-width":1.1});};
  person(-30,140);person(-14,150);person(510,70);
  {const [x,y]=iso(470,150,0);E(s,"circle",{cx:x,cy:y-30,r:3.6,fill:C3.g,stroke:C3.cream,"stroke-width":1.1});
   E(s,"path",{d:`M${x} ${y-26} L${x} ${y-12} M${x} ${y-12} L${x-4} ${y} M${x} ${y-12} L${x+4} ${y} M${x} ${y-23} L${x+6} ${y-18}`,fill:"none",stroke:C3.cream,"stroke-width":1.1});
   E(s,"rect",{x:x+5,y:y-21,width:5,height:8,fill:C3.gold});}
  // price tags
  {const [x,y]=iso(290,-4,112);T(s,x-6,y-30,"fossil, with tag",{"text-anchor":"end","font-size":13,fill:C3.dim});T(s,x-6,y-12,"NOK 27.20",{"text-anchor":"end","font-size":19,"font-weight":700});
   T(s,x+14,y-30,"electric, with tag",{"font-size":13,fill:C3.dim});T(s,x+14,y-12,"NOK 19.04",{"font-size":19,"font-weight":700,fill:C3.ev});}
  T(s,20,412,"rv. 70 · Nordsundbrua",{"font-size":12,fill:C3.dim,"font-family":"Roboto Mono"});
  // chart: revenue per passing against electric share
  const x0=690,x1=975,y0=70,y1=360,X=e=>x0+e*(x1-x0),Y=v=>y1-(v-17)/(29-17)*(y1-y0);
  E(s,"line",{x1:x0,y1:y1,x2:x1,y2:y1,stroke:C3.faint});E(s,"line",{x1:x0,y1:y0,x2:x0,y2:y1,stroke:C3.faint});
  [0,0.5,1].forEach(e=>T(s,X(e),y1+20,`${e*100}%`,{"text-anchor":"middle","font-size":12,fill:C3.dim}));
  T(s,(x0+x1)/2,y1+40,"electric share of passings",{"text-anchor":"middle","font-size":12,fill:C3.dim});
  [19,23,27].forEach(v=>T(s,x0-8,Y(v)+4,v,{"text-anchor":"end","font-size":12,fill:C3.dim}));
  T(s,x0,y0-22,"NOK per passing",{"font-size":12,fill:C3.dim});
  E(s,"rect",{x:x0,y:Y(27.20),width:x1-x0,height:Y(19.04)-Y(27.20),fill:"rgba(212,165,48,.08)"});
  E(s,"line",{x1:X(0),y1:Y(27.20),x2:X(1),y2:Y(19.04),stroke:C3.gold,"stroke-width":3});
  const e40=0.4,v40=27.20-8.16*e40;
  E(s,"line",{x1:X(e40),y1:Y(v40),x2:X(e40),y2:y1,stroke:C3.cream,"stroke-dasharray":"4 4","stroke-opacity":.6});
  E(s,"circle",{cx:X(e40),cy:Y(v40),r:6,fill:C3.cream});
  T(s,X(e40)+10,Y(v40)-12,`today, nationally: ${v40.toFixed(2)}`,{"font-size":13,"font-weight":600});
  E(s,"circle",{cx:X(1),cy:Y(19.04),r:6,fill:C3.ev});
  T(s,X(1)-6,Y(19.04)+24,"all electric: −30%",{"text-anchor":"end","font-size":13,fill:C3.ev,"font-weight":600});
  E(s,"circle",{cx:X(0),cy:Y(27.20),r:5,fill:C3.fos});
})();

// H2: three cases, one variable
(function(){const s=document.getElementById("h2");if(!s)return;
  const cases=[["Gothenburg, 2013","congestion charge","permanent",1,"rose · status quo bias","borjesson16"],
               ["Oslo region field trial","road-pricing trial","temporary",0,"little change","toi2179"],
               ["Oslo, 2019","toll restructuring","permanent",1,"share positive rose","toi2141"]];
  cases.forEach(([name,what,kind,up,res],i)=>{const x=40+i*250,base=250;
    T(s,x,30,name,{"font-size":17,"font-weight":700});T(s,x,50,what,{"font-size":13,fill:C3.dim});
    E(s,"rect",{x:x,y:64,width:96,height:22,rx:11,fill:kind==="permanent"?"rgba(212,165,48,.18)":"rgba(142,135,125,.18)",stroke:kind==="permanent"?C3.gold:C3.dim,"stroke-width":1});
    T(s,x+48,80,kind,{"text-anchor":"middle","font-size":12,fill:kind==="permanent"?C3.gold:C3.dim,stroke:"none"});
    const hb=60,ha=up?112:68;
    E(s,"rect",{x:x+10,y:base-hb,width:56,height:hb,fill:"none",stroke:C3.cream,"stroke-width":1.2});
    E(s,"rect",{x:x+96,y:base-ha,width:56,height:ha,fill:up?C3.red:"none",stroke:up?C3.red:C3.cream,"stroke-width":1.2,"fill-opacity":up?0.85:0});
    E(s,"line",{x1:x,y1:base,x2:x+180,y2:base,stroke:C3.faint});
    T(s,x+38,base+18,"before",{"text-anchor":"middle","font-size":12,fill:C3.dim});T(s,x+124,base+18,"after",{"text-anchor":"middle","font-size":12,fill:C3.dim});
    E(s,"path",{d:`M${x+70} ${base-hb/2} L${x+90} ${base-hb/2}`,stroke:C3.cream,"marker-end":"none","stroke-width":1.2});
    T(s,x+90,base+40,res,{"text-anchor":"middle","font-size":13.5,fill:up?C3.red:C3.cream,"font-weight":600});});
  // the test
  const x=790;E(s,"rect",{x:x-14,y:14,width:220,height:300,rx:10,fill:"rgba(210,65,43,.07)",stroke:C3.red,"stroke-width":1.2,"stroke-dasharray":"6 5"});
  T(s,x,42,"Kristiansund, 2026",{"font-size":17,"font-weight":700});T(s,x,62,"city package, 15 years",{"font-size":13,fill:C3.dim});
  E(s,"rect",{x:x,y:76,width:96,height:22,rx:11,fill:"rgba(212,165,48,.18)",stroke:C3.gold});T(s,x+48,92,"permanent",{"text-anchor":"middle","font-size":12,fill:C3.gold,stroke:"none"});
  T(s,x,134,"H1 · within persons:",{"font-size":13,fill:C3.cream,"font-weight":600});
  T(s,x,152,"does support rise as",{"font-size":13,fill:C3.body});T(s,x,169,"the charge becomes",{"font-size":13});T(s,x,186,"the status quo?",{"font-size":13});
  T(s,x,222,"H2 · randomised:",{"font-size":13,"font-weight":600});
  T(s,x,240,"does information on",{"font-size":13});T(s,x,257,"cost and revenue use",{"font-size":13});T(s,x,274,"move it on its own?",{"font-size":13});
  E(s,"path",{d:"M700 170 L760 170",stroke:C3.red,"stroke-width":2});E(s,"path",{d:"M752 164 L762 170 L752 176",fill:"none",stroke:C3.red,"stroke-width":2});
})();

// H3: the captive bridge on the real network
(function(){const s=document.getElementById("h3");if(!s||!TOWNS||!BRIDGE)return;
  const Tn=TOWNS.kristiansund,[bx0,by0,bx1,by1]=Tn.bbox,W=650,H=380,ox=0,oy=10,k=Math.min(W/(bx1-bx0),H/(by1-by0)),
    px=([a,b])=>[ox+(a-bx0)*k+(W-(bx1-bx0)*k)/2, oy+(by1-b)*k+(H-(by1-by0)*k)/2];
  Tn.sea.forEach(r=>E(s,"polygon",{points:r.map(q=>px(q).map(n=>n.toFixed(1)).join(",")).join(" "),fill:"rgba(233,225,208,.05)"}));
  Tn.roads.forEach(([maj,c])=>E(s,"polyline",{points:c.map(q=>px(q).map(n=>n.toFixed(1)).join(",")).join(" "),fill:"none",stroke:maj?"rgba(233,225,208,.55)":"rgba(233,225,208,.22)","stroke-width":maj?1.3:0.7}));
  Tn.points.forEach((q,i)=>{const [x,y]=px(q),far=BRIDGE.side[i]===1;E(s,"circle",{cx:x.toFixed(1),cy:y.toFixed(1),r:2,fill:far?C3.gold:C3.cream,"fill-opacity":far?0.95:0.55});});
  const [a,b]=BRIDGE.bridge_xy.map(px);E(s,"line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:C3.red,"stroke-width":6,"stroke-linecap":"round"});
  const mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2;E(s,"circle",{cx:mx,cy:my,r:11,fill:"none",stroke:C3.red,"stroke-width":2});
  E(s,"line",{x1:mx,y1:my,x2:mx-40,y2:my-70,stroke:C3.red,"stroke-width":1});T(s,mx-44,my-76,"Nordsundbrua · toll station",{"text-anchor":"end","font-size":14,"font-weight":600});
  // numbers
  const x=690;T(s,x,70,`${Math.round(BRIDGE.pairs_cut*100)}%`,{"font-size":76,"font-weight":900,fill:C3.red});
  T(s,x,98,"of junction pairs lose every",{"font-size":15});T(s,x,118,"road connection",{"font-size":15});
  T(s,x,200,`${Math.round(BRIDGE.buildings_far_side*100)}%`,{"font-size":76,"font-weight":900,fill:C3.gold});
  T(s,x,228,"of buildings lie on the",{"font-size":15});T(s,x,248,"far side of the charge",{"font-size":15});
  E(s,"circle",{cx:x+6,cy:290,r:5,fill:C3.cream,"fill-opacity":.55});T(s,x+20,295,"near side",{"font-size":13,fill:C3.dim});
  E(s,"circle",{cx:x+6,cy:314,r:5,fill:C3.gold});T(s,x+20,319,"far side",{"font-size":13,fill:C3.dim});
  T(s,x,360,`${BRIDGE.parts[0].toLocaleString("en")} and ${BRIDGE.parts[1].toLocaleString("en")} junctions`,{"font-size":13,fill:C3.dim});
  T(s,x,380,"in the two parts left behind",{"font-size":13,fill:C3.dim});
})();

// H4: the design in time
(function(){const s=document.getElementById("h4");if(!s)return;
  const x0=150,x1=980,X=y=>x0+(y-2024)/(2030.5-2024)*(x1-x0);
  for(let y=2024;y<=2030;y++){E(s,"line",{x1:X(y),y1:24,x2:X(y),y2:200,stroke:C3.faint});T(s,X(y),18,y,{"text-anchor":"middle","font-size":12,fill:C3.dim,"font-family":"Roboto Mono"});}
  E(s,"rect",{x:X(2027),y:28,width:X(2030)-X(2027),height:172,fill:"rgba(183,164,216,.06)",stroke:"none"});T(s,X(2028.5),214,"the PhD",{"text-anchor":"middle","font-size":12,fill:C3.fut});
  T(s,10,74,"Kristiansund",{"font-size":15,"font-weight":700});T(s,10,92,"test bed",{"font-size":12,fill:C3.dim});
  T(s,10,154,"Molde",{"font-size":15,"font-weight":700});T(s,10,172,"control",{"font-size":12,fill:C3.dim});
  E(s,"line",{x1:x0,y1:80,x2:x1,y2:80,stroke:C3.cream,"stroke-width":1});E(s,"line",{x1:x0,y1:160,x2:x1,y2:160,stroke:C3.cream,"stroke-width":1,"stroke-opacity":.5});
  const ev=(y,row,label,col,above=true)=>{const yy=row?160:80;E(s,"circle",{cx:X(y),cy:yy,r:6,fill:col,stroke:C3.g,"stroke-width":2});
    T(s,X(y),yy+(above?-14:24),label,{"text-anchor":"middle","font-size":12.5,fill:col===C3.cream?C3.cream:col});};
  ev(2024.3,0,"votes 26–19, 33–14",C3.cream);ev(2025.45,0,"Storting",C3.cream);
  E(s,"rect",{x:X(2026.4),y:72,width:X(2030.5)-X(2026.4),height:16,fill:"rgba(210,65,43,.22)"});T(s,X(2026.45),110,"collection under way",{"font-size":12.5,fill:C3.red});
  ev(2027.4,0,"wave 1",C3.red,true);ev(2027.4,1,"wave 1",C3.red,false);ev(2028.4,0,"wave 2 · same people",C3.red,true);
  [[2028,"A1"],[2029,"A2"],[2030,"A3"]].forEach(([y,t])=>{const x=X(y),yy=232;E(s,"path",{d:`M${x} ${yy-8} L${x+8} ${yy} L${x} ${yy+8} L${x-8} ${yy} Z`,fill:C3.gold});T(s,x+14,yy+5,t,{"font-size":13,fill:C3.gold,"font-weight":600});});
})();

// H5: the engine as exploded coloured layers
(function(){const s=document.getElementById("h5");if(!s)return;
  const W=320,D=190,cx=620,gap=78,base=20,iso=(u,v,z)=>[cx+(u-v)*0.866,z+(u+v)*0.5];
  const R=(seed=>()=>((seed=(seed*16807)%2147483647)/2147483647))(7);
  const layers=[["FUTURES","10³ worlds every plan is tested in",C3.fut,"futures"],["MONEY","revenue set against debt service",C3.gold,"money"],
    ["OPINIONS","support shifts with cost and information",C3.red,"opinion"],["PEOPLE AND VEHICLES","households and firms renew fleets",C3.ev,"agents"],
    ["NETWORK","zones, roads and the two stations",C3.cream,"net"]];
  [[0,0],[W,0],[W,D],[0,D]].forEach(([u,v])=>{const a=iso(u,v,base),b=iso(u,v,base+gap*4);E(s,"line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:C3.faint,"stroke-dasharray":"4 5"});});
  layers.map((d,i)=>[d,i]).reverse().forEach(([[name,line,col,kind],i])=>{const z=base+i*gap;
    E(s,"polygon",{points:[[0,0],[W,0],[W,D],[0,D]].map(([u,v])=>iso(u,v,z).map(n=>n.toFixed(1)).join(",")).join(" "),fill:col,"fill-opacity":0.12,stroke:col,"stroke-width":1.4});
    const g=E(s,"g",{});
    if(kind==="net"){for(let j=0;j<14;j++){const a=iso(20+R()*290,20+R()*160,z),b=iso(20+R()*290,20+R()*160,z);E(g,"line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:C3.cream,"stroke-opacity":.35});}
      [[150,60],[250,130]].forEach(([u,v])=>{const [x,y]=iso(u,v,z);E(g,"rect",{x:x-5,y:y-14,width:10,height:14,fill:C3.red});});}
    if(kind==="agents"){for(let j=0;j<40;j++){const [x,y]=iso(20+R()*290,20+R()*160,z),van=j%7===0,ev=R()<0.4;
      E(g,"rect",{x:x-(van?6:4),y:y-(van?6:4),width:van?12:8,height:van?6:4,fill:van?C3.van:(ev?C3.ev:C3.fos)});}}
    if(kind==="opinion"){for(let j=0;j<28;j++){const [x,y]=iso(20+R()*290,20+R()*160,z),yes=R()<0.55;T(g,x,y,yes?"✓":"✗",{"font-size":11,fill:yes?C3.cream:C3.red,stroke:"none","text-anchor":"middle"});}}
    if(kind==="money"){for(let j=0;j<10;j++){const u=30+j*28,h=46-j*3.4,[x,y]=iso(u,100,z);E(g,"rect",{x:x-6,y:y-h,width:12,height:h,fill:C3.gold,"fill-opacity":.85});}
      const a=iso(20,100,z+32),b=iso(310,100,z+32);E(g,"line",{x1:a[0],y1:a[1]-32+32,x2:b[0],y2:b[1],stroke:C3.red,"stroke-dasharray":"5 4","stroke-width":1.4});}
    if(kind==="futures"){const [x,y]=iso(160,100,z);for(let j=0;j<18;j++){const ang=-Math.PI*0.95+j*Math.PI*0.9/17;E(g,"line",{x1:x,y1:y,x2:x+Math.cos(ang)*120,y2:y+Math.sin(ang)*48,stroke:C3.fut,"stroke-opacity":.7});}}
    const [ax,ay]=iso(0,D*0.55,z);T(s,30,ay-8,name,{"font-size":15,"font-weight":800,fill:col});T(s,30,ay+12,line,{"font-size":13,fill:C3.body});
  });
  T(s,30,462,"each year passes up the stack; the stack is replayed in every future",{"font-size":12,fill:C3.dim,"font-family":"Roboto Mono"});
})();

// H6: adaptive pathways metro map
(function(){const s=document.getElementById("h6");if(!s)return;
  const x0=170,x1=960,X=y=>x0+(y-2027)/(2050-2027)*(x1-x0);
  [2027,2030,2035,2040,2045,2050].forEach(y=>{E(s,"line",{x1:X(y),y1:16,x2:X(y),y2:236,stroke:C3.faint});T(s,X(y),256,y,{"text-anchor":"middle","font-size":12,fill:C3.dim,"font-family":"Roboto Mono"});});
  const lines=[["package revision",C3.gold,36,2027,2036],["electric rate change",C3.ev,92,2027,2041],["distance-based charge",C3.van,148,2031,2050],["earmarked revenue",C3.fut,204,2029,2050]];
  lines.forEach(([n,c,y,a,b])=>{T(s,10,y+5,n,{"font-size":13.5,fill:c,"font-weight":600});E(s,"line",{x1:X(a),y1:y,x2:X(b),y2:y,stroke:c,"stroke-width":7,"stroke-linecap":"round"});
    if(b<2050){E(s,"line",{x1:X(b)+8,y1:y-14,x2:X(b)+8,y2:y+14,stroke:C3.red,"stroke-width":4});}});
  // transfers at signposts
  const tr=[[2034,36,148],[2036,36,204],[2039,92,148],[2031,92,204]];
  tr.forEach(([y,a,b])=>{E(s,"line",{x1:X(y),y1:a,x2:X(y),y2:b,stroke:C3.cream,"stroke-width":2,"stroke-dasharray":"3 3"});
    [a,b].forEach(yy=>E(s,"circle",{cx:X(y),cy:yy,r:6.5,fill:C3.g,stroke:C3.cream,"stroke-width":2}));});
  // legend
  E(s,"circle",{cx:180,cy:292,r:6,fill:C3.g,stroke:C3.cream,"stroke-width":2});T(s,194,297,"signpost: switch here",{"font-size":12.5,fill:C3.dim});
  E(s,"line",{x1:372,y1:282,x2:372,y2:302,stroke:C3.red,"stroke-width":4});T(s,384,297,"tipping point: support below threshold, or revenue below debt service",{"font-size":12.5,fill:C3.dim});
})();
