// Portfolio plates p6 to p9, drawn from DATA (study.json) and DCM (transplan_study.json "dcm").

// P6 six of six recovered: true value as a tick, estimate with one standard error (sage family)
(function(){const s=document.getElementById("p6");if(!s||!DCM)return;
  const L=LineArt(s,Object.assign({sw:1},LINEART_THEMES.oxblood)),C=L.C;
  const names={ASC_ev:"electric car constant",ASC_bus:"bus constant",ASC_bike:"bike constant",B_TIME:"time, per minute",B_COST:"cost, per NOK",B_WAIT:"wait, per minute"};
  const keys=Object.keys(names),x0=430,x1=930,X=z=>x0+(z+2.5)/5*(x1-x0);
  [-2,-1,0,1,2].forEach(z=>{L.line(s,`M${X(z)} 30 L${X(z)} 330`,{"stroke-opacity":z===0?.6:.15,"stroke-dasharray":z===0?"":"3 4"});
    L.text(s,X(z),356,z===0?"true value":(z>0?"+":"−")+Math.abs(z)+" s.e.",{"text-anchor":"middle","font-size":14,fill:C.dim,"font-family":"Inter"});});
  keys.forEach((k,i)=>{const y=52+i*50,b=DCM.beta[k],se=DCM.std_err[k],t=DCM.true[k],z=(b-t)/se;
    L.text(s,0,y+5,names[k],{"font-size":17,"font-family":"Inter"});
    L.text(s,250,y+5,`${b.toFixed(Math.abs(b)<0.1?4:3)} ± ${se.toFixed(Math.abs(b)<0.1?4:3)}`,{"font-size":15,fill:C.dim,"font-family":"Roboto Mono"});
    L.line(s,`M${X(z-1)} ${y} L${X(z+1)} ${y}`,{"stroke-width":2.2});
    L.line(s,`M${X(z-1)} ${y-6} L${X(z-1)} ${y+6} M${X(z+1)} ${y-6} L${X(z+1)} ${y+6}`,{"stroke-width":1.4});
    L.line(s,`M${X(0)} ${y-12} L${X(0)} ${y+12}`,{stroke:C.accent,"stroke-width":2.4});
    L.el(s,"circle",{cx:X(z),cy:y,r:6,fill:C.cream});});
})();

// P7 the price of robustness: futures met against net public money per commuter and year
(function(){const s=document.getElementById("p7");if(!s||!DATA)return;
  const L=LineArt(s,Object.assign({sw:1},LINEART_THEMES.oxblood)),C=L.C;
  const P=DATA.packages_list.filter(p=>p.id!=="no_policy").map(p=>Object.assign({},p,{n:Math.round(p.robustness*60),net:p.subsidy_nok-p.toll_nok_rev}));
  const nets=P.map(p=>p.net),lo=Math.min(...nets),hi=Math.max(...nets),pad=800;
  const x0=110,x1=960,y0=70,y1=470,X=n=>x0+n/60*(x1-x0),Y=v=>y1-(v-(lo-pad))/((hi+pad)-(lo-pad))*(y1-y0);
  L.line(s,`M${x0} ${y1} L${x1} ${y1} M${x0} ${y0} L${x0} ${y1}`,{"stroke-opacity":.5});
  L.line(s,`M${x0} ${Y(0)} L${x1} ${Y(0)}`,{"stroke-dasharray":"5 5","stroke-opacity":.7});
  L.text(s,x1,Y(0)-10,"public money breaks even",{"text-anchor":"end","font-size":14,fill:C.dim});
  L.text(s,x0+10,y0+16,"costs the public",{"font-size":14,fill:C.dim});L.text(s,x0+10,y1-12,"raises money",{"font-size":14,fill:C.dim});
  [0,15,30,45,60].forEach(n=>L.text(s,X(n),y1+26,n,{"text-anchor":"middle","font-size":14,fill:C.dim}));
  L.text(s,(x0+x1)/2,y1+56,"futures in which the package meets the 2050 target, of 60",{"text-anchor":"middle","font-size":15});
  const step=Math.pow(10,Math.floor(Math.log10(hi-lo)))*0.5;
  for(let v=Math.ceil((lo-pad)/step)*step;v<=hi+pad;v+=step)L.text(s,x0-12,Y(v)+5,Math.round(Math.abs(v)).toLocaleString("en"),{"text-anchor":"end","font-size":13,fill:C.dim});
  P.forEach(p=>{const surv=p.robustness>=0.55-1e-9&&p.accept>=0.5;
    L.el(s,"circle",{cx:X(p.n),cy:Y(p.net),r:surv?8:6,fill:surv?C.accent:"none",stroke:surv?C.accent:C.cream,"stroke-width":1.2,"stroke-opacity":surv?1:.7});
    if(surv)L.text(s,X(p.n)+12,Y(p.net)+5,p.id,{"font-size":15,fill:C.cream});});
  L.text(s,x1,24,"filled: survives the filter",{"text-anchor":"end","font-size":14,fill:C.accent});
})();

// P8 when cars last: futures by vehicle lifetime and telework, hostile ones filled, the box that holds most
(function(){const s=document.getElementById("p8");if(!s||!DATA)return;
  const L=LineArt(s,Object.assign({sw:1},LINEART_THEMES.oxblood)),C=L.C,H=DATA.hostile,B=H.box.box;
  const iT=H.dims.indexOf("telework_2050"),iL=H.dims.indexOf("vehicle_lifetime");
  const x0=110,x1=960,y0=70,y1=470,X=v=>x0+(v-10)/8*(x1-x0),Y=v=>y1-v/0.3*(y1-y0);
  L.line(s,`M${x0} ${y1} L${x1} ${y1} M${x0} ${y0} L${x0} ${y1}`,{"stroke-opacity":.5});
  [10,12,14,16,18].forEach(v=>L.text(s,X(v),y1+26,v,{"text-anchor":"middle","font-size":14,fill:C.dim}));
  [0,0.1,0.2,0.3].forEach(v=>L.text(s,x0-12,Y(v)+5,Math.round(v*100)+"%",{"text-anchor":"end","font-size":14,fill:C.dim}));
  L.text(s,(x0+x1)/2,y1+56,"vehicle lifetime, years",{"text-anchor":"middle","font-size":15});
  L.text(s,x0-100,24,"telework share of commute days, 2050",{"font-size":14,fill:C.dim});
  const bl=B.vehicle_lifetime[1],bt=B.telework_2050[1];
  L.el(s,"rect",{x:X(bl),y:Y(bt),width:x1-X(bl),height:y1-Y(bt),fill:"rgba(217,115,78,.10)",stroke:C.accent,"stroke-width":1.4,"stroke-dasharray":"6 5"});
  L.text(s,x1-10,Y(bt)+24,`${H.box.hits} of ${H.box.inside} futures in this box defeat every package`,{"text-anchor":"end","font-size":16,fill:C.accent});
  H.points.forEach(r=>{const h=r[2];L.el(s,"circle",{cx:X(r[iL]),cy:Y(r[iT]),r:h?7:5.5,fill:h?C.accent:"none",stroke:h?C.accent:C.cream,"stroke-width":1.1,"stroke-opacity":h?1:.7});});
  L.text(s,x1,24,`filled: no package meets the target (${H.n} of 60)`,{"text-anchor":"end","font-size":14,fill:C.accent});
})();

// P9 thirty-six months: one row per strand, an accent diamond at each submission
(function(){const s=document.getElementById("p9");if(!s)return;
  const L=LineArt(s,Object.assign({sw:1},LINEART_THEMES.oxblood)),C=L.C,x0=230,x1=980,X=m=>x0+m/36*(x1-x0);
  const rows=[["PhD courses",[[1,6],[13,16]]],["survey: design, pilot, field",[[1,9]]],["engine on synthetic, then real",[[1,12],[13,22]]],["calibration and 2010 to 2025 test",[[14,22]]],
    ["research stay",[[19,24]]],["ensemble, search, signposts",[[25,32]]],["freight test",[[29,32]]],["thesis",[[30,36]]]];
  [0,12,24,36].forEach(m=>{L.line(s,`M${X(m)} 20 L${X(m)} 250`,{"stroke-opacity":m%12?0.15:0.35});});
  ["YEAR 1","YEAR 2","YEAR 3"].forEach((t,i)=>L.text(s,X(i*12+6),20,t,{"text-anchor":"middle","font-size":14,"letter-spacing":".1em",fill:C.dim}));
  rows.forEach(([name,segs],i)=>{const y=46+i*26;L.text(s,0,y+5,name,{"font-size":15});
    segs.forEach(([a,b])=>L.el(s,"rect",{x:X(a-1),y:y-7,width:X(b)-X(a-1),height:14,rx:3,fill:"none",stroke:C.cream,"stroke-width":1.1}));});
  [[12,"A1"],[24,"A2"],[31,"A3"]].forEach(([m,t])=>{const x=X(m),y=262;L.el(s,"path",{d:`M${x} ${y-9} L${x+9} ${y} L${x} ${y+9} L${x-9} ${y} Z`,fill:C.accent});
    L.text(s,x,y+30,t+" submitted",{"text-anchor":"middle","font-size":14,fill:C.accent});});
})();
