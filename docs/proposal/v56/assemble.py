import json, base64
E=json.load(open("figs_extra.json")); FIG2,FIG3,FIG5B=E["FIG2"],E["FIG3"],E["FIG5B"]
exec(open("fig1_parts.py").read())   # FIG1B
RF=open("rf_inner.txt").read()
F1A=open("f1a_inner.txt").read()
MAP="data:image/jpeg;base64,"+base64.b64encode(open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/kristiansund_map.jpg","rb").read()).decode()
CSS=open("page1.css").read()+r"""
.sheet{page-break-after:always}
.eq{font-family:'JetBrains Mono',monospace;font-size:13px;background:#241217;border-left:2px solid var(--gold);padding:10px 16px;margin:8px 0;line-height:1.7}
.ttable{width:100%;border-collapse:collapse;margin:6px 0 14px;font-size:12.5px}
.ttable th{font-family:Montserrat;font-weight:700;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--mut);text-align:left;padding:8px 12px;border-bottom:1px solid var(--line)}
.ttable td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.4}
.ttable td.k{color:var(--mut)}
.tools{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:8px 0 14px}
.tcol{padding:13px 13px 15px;border-left:1px solid var(--line)}
.tcol:first-child{border-left:none}
.tcat{font-family:Montserrat;font-weight:800;font-size:11.5px;letter-spacing:1.3px;color:var(--gold);text-transform:uppercase;margin-bottom:8px}
.ttool{font-family:Montserrat;font-weight:700;font-size:13px}
.ttool.s{font-weight:500;font-size:11.5px;color:var(--mut)}
.trole{font-family:Spectral;font-size:12px;line-height:1.38;opacity:.84;margin:7px 0 6px}
.tart{font-family:JetBrains Mono;font-size:10px;color:var(--teal)}
.lstack{display:flex;flex-direction:column;gap:3px;margin-top:4px}
.lstrip{display:grid;grid-template-columns:188px 1fr;background:#241217;border:1px solid var(--line);border-radius:4px;overflow:hidden}
.llabel{padding:7px 11px;border-right:1px solid var(--line);background:#1f1014}
.lname{font-family:Montserrat;font-weight:800;font-size:12px}
.lchip{font-family:JetBrains Mono;font-size:8px;letter-spacing:.3px;border:1px solid;border-radius:3px;padding:1px 5px}
.ltool{font-family:JetBrains Mono;font-size:9px;opacity:.8;margin-top:3px}
.lrole{font-family:Spectral;font-style:italic;font-size:10.5px;color:var(--mut)}
.lband{min-height:72px;background-size:820px auto;background-position:28% -130px}
.lband svg{display:block;height:72px}
.leg3wrap{display:flex;gap:18px;flex-wrap:wrap;margin-top:8px}
.l3{font-family:Spectral;font-size:11.5px}.l3 b{font-weight:600}.d3{width:11px;height:11px;border-radius:50%;display:inline-block;margin-right:5px;vertical-align:-1px}.s3{color:var(--mut);font-family:JetBrains Mono;font-size:10px}
.f3eq{font-family:JetBrains Mono;font-size:11.5px;color:var(--gold);margin-top:8px;border-top:1px solid var(--line);padding-top:8px}
.f5bnote{font-family:Spectral;font-size:12px;margin-top:6px;color:var(--ink);opacity:.9}.f5bnote b{color:var(--gold)}
.twocol{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.rfwrap{background:#241217;border:1px solid var(--line);border-radius:6px;padding:10px;margin:4px 0}
.small{font-size:12px;line-height:1.5;color:var(--ink);opacity:.9}
.refcol{column-count:2;column-gap:26px;font-size:10.5px;line-height:1.45}
.ref{break-inside:avoid;margin-bottom:7px}.ref .rk{font-family:JetBrains Mono;color:var(--gold)}
h3{font-family:Montserrat;font-weight:700;font-size:14px;margin:12px 0 4px;letter-spacing:.2px}
"""
def sheet(num,kicker,title,title_g,body): 
    tg=title.replace(title_g,f'<span class="g">{title_g}</span>') if title_g else title
    return f'<section class="sheet"><div class="secnum">{kicker}</div><h2>{tg}</h2>{body}</section>'

# ---- PAGE 1 ----
p1_top=f'''<div class="kick">Research proposal · TRANSPLAN · Molde University College</div>
<div class="doctitle">From end states to <span class="g">pathways</span></div>
<div class="docsub">Estimated acceptance, agents with memory, and robust road-pricing paths to a low-carbon Norway in 2050</div>
<div class="byline">Arshad Akhtar Abbasia · PhD in Transport Modelling for Sustainability Transitions · PhD programme in Logistics</div>
<div class="hr"></div>'''
p1_body=f'''<p>Norway appraises transport with a national model system that computes an equilibrium for a chosen year. Asked what 2050 looks like under a set of assumptions, it answers carefully. Asked how the country gets there, and which routes fail on the way, it is silent by construction. TØI’s own review says as much: the current models are <span class="b">static and macroscopic</span>, and less suited to dynamic questions [toi1819]. The path to 2050 is governed by what an equilibrium does not carry: a vehicle fleet that turns over slowly, public acceptance that persists or erodes, and debt repaid on a schedule.</p>
<p>Road pricing shows the problem in its sharpest form. It is named among the levers for the next National Transport Plan, where TRANSPLAN’s first deliverable argues the plan must be <span class="b">realistic and goal-directed</span> rather than a wish list [toi2172]; yet the national reform has stalled. Tolls raised NOK 16.8 billion in 2025, about 62% in city packages, against toll-company debt near NOK 78 billion [svv25, dok15]. Every revision meets a public that has voted against tolls before: a single-issue anti-toll party won 16.7% in Bergen in 2019 [snl19]. Whether a 2050 plan is feasible depends on the order in which instruments arrive and whether people accept each step. <span class="b">That is a question about paths.</span></p>
<div class="rqbox"><div class="mq">Main question. Which sequences of road-pricing instruments reach a desirable 2050 on emissions, finance and accessibility while staying acceptable to the people and firms who pay, across deep uncertainty; and which signals tell planners when to switch?</div>
<div class="rq"><b>RQ1 · method (A1)</b>How can choice models estimated on real data drive agents that carry state year to year, so strategic end states become pathways?</div>
<div class="rq"><b>RQ2 · behaviour (A2)</b>Does acceptance persist once a charge is permanent, and does information move it independently of experience?</div>
<div class="rq"><b>RQ3 · planning (A3)</b>Which pathways, for passengers and for freight, are robust; what acceptance margin does each survive; and which signposts give lead time before one fails?</div></div>
<p><span class="b">What already exists.</span> I have a working prototype and a first measured result. At the Kristiansund tariff a zero-emission car with a tag pays NOK 19.04 against NOK 27.20, so each electric crossing earns NOK 8.16, or 30%, less [vegamot]. At today’s national share of four electric passings in ten, a crossing already earns about 12% less than in a fossil fleet; in an all-electric fleet it earns 30% less while the debt is unchanged. On the road network, the toll-free Atlantic Ocean Tunnel lets some crossings avoid both stations; Article 1 counts that share ([N1]), so exposure is measured on the network, not assumed uniform.</p>
<div class="twocol"><div class="rfwrap">{F1A}</div>
<div class="plate"><span class="platelabel teal">What a crossing earns</span>{FIG1B}</div></div>
<div class="handoff">→ So Norway needs the dynamic layer TØI calls for. What should it be, and who has built the pieces?</div>
<div class="foot"><span>Arshad Akhtar Abbasia</span><span>From end states to pathways</span><span class="r">github.com/Astheno-sphere/computational_logistics · 1 / 6</span></div>'''
page1=f'<section class="sheet">{p1_top}<div class="secnum">01 · THE PROBLEM</div><h2>What an equilibrium <span class="g">cannot carry</span></h2>{p1_body}</section>'

# ---- PAGE 2 ----
p2=f'''<p>The national system has three parts a candidate must name: <span class="b">NTM6</span>, the national passenger model for trips over 70 km; <span class="b">RTM</span>, the regional passenger model; and the national freight model, <span class="b">Nasjonal godsmodell (NGM)</span>, with its commodity-flow matrices and transport-chain costs [toi1819, ngm]. These anchor the National Transport Plan and are trusted for point appraisal. TØI’s forward-looking review recommends not replacing them but building dynamic models alongside them [toi1819]; the institute has begun, with a MATSim-based agent assignment for Greater Oslo, tramodsim, and an activity-based model for Trondheim [tramodsim]. This PhD joins that line rather than importing a method from outside it. It supplies the exploratory, stress-testing layer that sequences instruments across thousands of futures and reports where each sequence fails, so the national models keep producing the appraisal the agencies rely on while this layer supplies the robustness and failure conditions they are not built to give.</p>
<table class="ttable"><tr><th>The position asks for</th><th>This proposal answers with</th></tr>
<tr><td class="k">Desirable futures under deep uncertainty</td><td>10³ futures, satisficing targets, uncertainty decomposed by source</td></tr>
<tr><td class="k">DCM integrated with ABM</td><td>Choice models estimated on real survey data drive agents whose acceptance and fleet carry over year to year</td></tr>
<tr><td class="k">Behaviour under low-carbon scenarios to 2050</td><td>Emissions an explicit objective; passenger acceptance and carrier mode choice both estimated; freight vehicles turn over by class, with load factors and empty running from NGM</td></tr>
<tr><td class="k">Backcasting and pathways, not one forecast</td><td>2050 targets defined on page 3; instrument orders searched backward from them</td></tr>
<tr><td class="k">Methodological and practical contributions</td><td>Three testable claims and a named decision: revising the zero-emission discount and tariff</td></tr></table>
<p><span class="b">The gap.</span> Strategic models give end states and NGM gives freight chains; neither carries acceptance. Norwegian agent work assigns traffic with MATSim but takes acceptance as given [tramodsim]. Le Pira, Marcucci and Gatta integrated discrete choice and agent-based models to evaluate the acceptability of urban freight policy [lepira]; their agents are stakeholder groups negotiating in rounds, not a population living through calendar time. Adaptive pathway methods sequence actions against tipping points [dapp, haasnoot] but treat acceptance as an external scenario. The deep-uncertainty frontier runs ensembles over transport agent models, most recently on a fictional city with acceptance left out [fuhrer]. The road-pricing acceptance evidence is careful and mostly static, and hybrid choice with a latent acceptance variable is now an established way to read it [hybridaccept, odeck08, borjesson16, toi2179]. <span class="b">Nobody has estimated acceptance on real data, carried it in agents over calendar time, and let it decide which passenger and freight pathways survive.</span></p>
<div class="heart">The question beneath the whole proposal is prior to any pathway: is public acceptance a measurable quantity that can be estimated on real data and carried forward in time, or not? The thesis answers that first; the ensemble and the robust front are what the answer is then used for, not the other way round.</div>
<div class="claims">
<div class="claim"><div class="cn">1</div><div class="ct">Acceptance, estimated and carried, as an admissibility condition</div><p>First that acceptance can be estimated on real survey data and shown to persist (or not) between waves; then that a pathway counts only if that estimated acceptance stays above a threshold at every step, with the largest shift it survives reported as its acceptance margin — a result, not an assumption.</p></div>
<div class="claim"><div class="cn">2</div><div class="ct">Uncertainty decomposed by source over a policy path</div><p>The spread in 2050 outcomes is split, year by year, into behavioural parameters, external futures and the choice of path, so planners see which uncertainty more data can reduce and which only adaptation can.</p></div>
<div class="claim"><div class="cn">3</div><div class="ct">Signposts validated twice, and ordered across modes</div><p>Signals that a pathway is failing are scored on held-out futures for lead time and false alarms, then against dated events that happened; and the passenger and freight signposts are compared, because the slower fleet decides which fires first.</p></div></div>
<div class="plate" style="margin-top:4px"><span class="platelabel">One network, the layers it must carry</span>{FIG2}
<div class="figcap">Six layers over one Kristiansund street graph. The network is real; fleet, emissions and revenue come from the prototype; <span style="color:#D4835C">choice and acceptance are the quantities this PhD sets out to estimate</span> — drawn dashed because they are not computed yet. An equilibrium collapses all of this into one number for one year.</div></div>
<div class="handoff">→ Here is that layer, written down.</div>
<div class="foot"><span>Arshad Akhtar Abbasia</span><span>Fit, gap and what is new</span><span class="r">github.com/Astheno-sphere/computational_logistics · 2 / 6</span></div>'''
page2='<section class="sheet"><div class="secnum">02 &middot; FIT, GAP AND WHAT IS NEW</div><h2>A dynamic layer <span class="g">beside</span> the national models</h2>'+p2+'</section>'

open("content_p12.txt","w").write(page1+"\n@@@\n"+page2)
# stash CSS + parts for next step
CSS=CSS+open("_RFCSS.txt").read()+"""
.twocol{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.lab{display:inline-block;font-family:Montserrat;font-weight:700;font-size:11px;letter-spacing:1.6px;color:#140a0e;background:var(--gold);padding:3px 10px;border-radius:3px;text-transform:uppercase}
.mapwrap{position:relative;margin-top:9px;border:1px solid var(--line);border-radius:5px;overflow:hidden}
.mapwrap img{width:100%;display:block}
.maptag{position:absolute;top:9px;left:11px;font-family:Montserrat;font-weight:700;font-size:10px;letter-spacing:.5px;color:var(--ink)}
.exrow{display:flex;gap:13px;align-items:center;margin-top:8px;font-family:Montserrat;font-size:10px;color:var(--mut);flex-wrap:wrap}
.exrow .sw{width:11px;height:11px;border-radius:2px;display:inline-block;margin-right:5px;vertical-align:-2px}
.cap{font-family:Spectral;font-style:italic;font-size:12px;color:var(--ink);opacity:.9;margin-top:9px}
"""
open("_CSS.txt","w").write(CSS)
print("p1+p2 assembled")
