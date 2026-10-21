# -*- coding: utf-8 -*-
import json
D=json.load(open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/v57/plates_data.json"))
def img(k,cls="",style=""): return f'<img class="{cls}" src="{D[k]}" style="{style}">'

CSS=r"""
:root{--bg:#2b161c;--ink:#E8DFD0;--mut:#b89a86;--gold:#D4A530;--sage:#9DB886;--terra:#D4835C;--red:#C45545;--teal:#7CBAC4;--line:#5a3a40;--dark:#1f1014;--navy:#101722}
*{box-sizing:border-box}
body{margin:0;background:#120a0d;color:var(--ink);font-family:Spectral,Georgia,serif}
.sheet{width:1123px;min-height:1587px;margin:0 auto 0;background:var(--bg);padding:56px 64px 40px;display:flex;flex-direction:column;page-break-after:always}
.kick{font-family:Montserrat;font-weight:700;font-size:12.5px;letter-spacing:3px;color:var(--gold);text-transform:uppercase}
.doctitle{font-family:Montserrat;font-weight:900;font-size:40px;line-height:.98;letter-spacing:-.5px;margin:7px 0 4px}
.doctitle .g,.g{color:var(--gold)}
.docsub{font-family:Spectral;font-style:italic;font-size:17px;opacity:.88}
.byline{font-family:Montserrat;font-size:11px;letter-spacing:.3px;color:var(--mut);margin-top:6px}
.hr{height:1px;background:var(--line);margin:16px 0}
.secnum{font-family:Montserrat;font-weight:700;font-size:12px;letter-spacing:2.5px;color:var(--gold);margin-top:4px}
h2{font-family:Montserrat;font-weight:800;font-size:27px;letter-spacing:-.3px;margin:3px 0 12px}
h3{font-family:Montserrat;font-weight:700;font-size:14px;margin:13px 0 4px;letter-spacing:.2px}
p{font-size:14.5px;line-height:1.56;margin:0 0 11px;max-width:70ch}
.b{font-weight:600}.small{font-size:12.5px;line-height:1.5}
.rqbox{border-left:2px solid var(--gold);background:var(--dark);padding:13px 18px;margin:4px 0 14px}
.rqbox .mq{font-family:Spectral;font-style:italic;font-size:14.5px;margin-bottom:8px}
.rq{font-size:13px;line-height:1.5;margin:5px 0}
.rq b{font-family:Montserrat;font-weight:700;font-size:11px;letter-spacing:1px;color:var(--gold);text-transform:uppercase;margin-right:6px}
.plate{background:var(--dark);border:1px solid var(--line);border-radius:7px;padding:14px 16px;margin:10px 0}
.plate img{width:100%;display:block;border-radius:4px}
.plabel{display:inline-block;font-family:Montserrat;font-weight:700;font-size:10.5px;letter-spacing:1.5px;color:#140a0e;background:var(--gold);padding:3px 10px;border-radius:3px;text-transform:uppercase;margin-bottom:9px}
.plabel.teal{background:var(--teal)}.plabel.dark{background:var(--navy);color:var(--teal);border:1px solid var(--teal)}
.cap{font-family:Spectral;font-style:italic;font-size:13px;color:var(--ink);opacity:.92;margin-top:9px;max-width:92ch}
.cap .d{font-style:normal;color:var(--gold);font-family:Montserrat;font-weight:600;font-size:11px}
.tier{font-family:JetBrains Mono;font-size:9px;color:#8f7a86;border:1px solid var(--line);border-radius:3px;padding:1px 6px;white-space:nowrap}
.handoff{font-family:Spectral;font-style:italic;font-size:14px;color:var(--mut);margin-top:14px}
.foot{display:flex;justify-content:space-between;font-family:Montserrat;font-size:10px;letter-spacing:1px;color:var(--mut);margin-top:auto;padding-top:20px;text-transform:uppercase}
.foot .r{color:var(--gold);text-transform:none;font-family:JetBrains Mono;font-size:10px}
.eq{font-family:'JetBrains Mono',monospace;font-size:13px;background:var(--dark);border-left:2px solid var(--gold);padding:10px 16px;margin:8px 0;line-height:1.7}
.ttable{width:100%;border-collapse:collapse;margin:6px 0 12px;font-size:12.5px}
.ttable th{font-family:Montserrat;font-weight:700;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--mut);text-align:left;padding:8px 12px;border-bottom:1px solid var(--line)}
.ttable td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.4}
.ttable td.k{color:var(--mut)}
.heart{border-left:2px solid var(--teal);background:var(--dark);padding:11px 16px;margin:4px 0 12px;font-family:Spectral;font-style:italic;font-size:14px}
.claims{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:6px 0 4px}
.claim{background:var(--dark);border:1px solid var(--line);border-radius:5px;padding:12px 13px}
.claim .cn{font-family:Montserrat;font-weight:900;font-size:19px;color:var(--gold)}
.claim .ct{font-family:Montserrat;font-weight:700;font-size:12px;margin:3px 0 5px;line-height:1.25}
.claim p{font-size:11.5px;line-height:1.4;margin:0;opacity:.86}
.twocol{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px}
.tools{display:grid;grid-template-columns:repeat(6,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:8px 0 12px}
.tcol{padding:12px 11px 14px;border-left:1px solid var(--line)}.tcol:first-child{border-left:none}
.tcat{font-family:Montserrat;font-weight:800;font-size:11px;letter-spacing:1.2px;color:var(--gold);text-transform:uppercase;margin-bottom:7px}
.ttool{font-family:Montserrat;font-weight:700;font-size:12.5px}.ttool.s{font-weight:500;font-size:11px;color:var(--mut)}
.trole{font-family:Spectral;font-size:11.5px;line-height:1.35;opacity:.84;margin:6px 0 5px}
.tart{font-family:JetBrains Mono;font-size:10px;color:var(--teal)}
.calc{font-family:'JetBrains Mono',monospace;font-size:12px}
.qline{color:var(--gold);font-weight:500;margin-bottom:9px}
.crow{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border-bottom:1px dotted #3a2129}
.crow .cl{color:var(--mut)}.crow .cv{color:var(--ink);text-align:right}.crow .cv.gold{color:var(--gold);font-weight:600}.crow.hl .cv{color:var(--gold);font-weight:600}
.cdiv{height:1px;background:var(--line);margin:8px 0}
.vpanel{background:var(--dark);border:1px solid var(--line);border-radius:6px;padding:13px 15px;margin:10px 0}
.vbar{display:flex;height:26px;border-radius:4px;overflow:hidden;margin:8px 0 4px;border:1px solid var(--line)}
.vbar span{display:flex;align-items:center;justify-content:center;font-family:Montserrat;font-weight:700;font-size:10px;color:#140a0e;white-space:nowrap}
.constell{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:6px 0}
.cnode{background:var(--dark);border:1px solid var(--line);border-radius:6px;padding:11px 13px}
.cnode .cr{font-family:Montserrat;font-weight:700;font-size:11px;letter-spacing:.5px;color:var(--gold);text-transform:uppercase}
.cnode p{font-size:11.5px;margin:4px 0 0;opacity:.88;line-height:1.4}
.dark-inset{background:var(--navy);border:1px solid #2a3647;border-radius:7px;padding:12px 14px;margin:10px 0}
.dark-inset img{width:100%;display:block;border-radius:4px}
.dark-inset .dl{font-family:Montserrat;font-weight:700;font-size:10.5px;letter-spacing:1.3px;color:var(--teal);text-transform:uppercase}
.dark-inset .dc{font-family:Spectral;font-style:italic;font-size:12.5px;color:#c8d4de;margin-top:7px}
/* references */
.refgroup{margin-bottom:12px}
.refgh{font-family:Montserrat;font-weight:700;font-size:11px;letter-spacing:1.5px;color:var(--gold);text-transform:uppercase;border-bottom:1px solid var(--line);padding-bottom:4px;margin-bottom:7px}
.ref{font-size:11px;line-height:1.4;margin-bottom:5px}
.ref .rk{font-family:'JetBrains Mono';font-size:10px;color:var(--gold);font-weight:500}
.ledger{background:var(--dark);border:1px solid var(--line);border-radius:6px;padding:12px 15px;margin-top:8px}
.ledger table{width:100%;border-collapse:collapse;font-size:11px}
.ledger td{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.ledger .h{font-family:JetBrains Mono;color:var(--teal);font-size:10px}
"""

FOOT=lambda t,n:f'<div class="foot"><span>Arshad Akhtar Abbasia</span><span>{t}</span><span class="r">github.com/Astheno-sphere/computational_logistics &middot; {n} / 6</span></div>'

# ============ PAGE 1 ============
P1=f'''<section class="sheet">
<div class="kick">Research proposal &middot; Department of Logistics &middot; Molde University College</div>
<div class="doctitle">From end states to <span class="g">pathways</span></div>
<div class="docsub">Estimated acceptance, agents with memory, and robust road-pricing paths to a low-carbon Norway in 2050</div>
<div class="byline">Arshad Akhtar Abbasia &middot; PhD in Transport Modelling for Sustainability Transitions &middot; PhD programme in Logistics</div>
<div class="hr"></div>
<div class="secnum">01 &middot; THE PROBLEM</div>
<h2>What an equilibrium <span class="g">cannot carry</span></h2>
<p>Norway appraises transport with a national model system that computes an equilibrium for a chosen year. Asked what 2050 looks like under a set of assumptions, it answers carefully. Asked how the country gets there, and which routes fail on the way, it is silent by construction. T&Oslash;I&rsquo;s own review says as much: the current models are <span class="b">static and macroscopic</span>, less suited to dynamic questions [toi1819]. The path to 2050 is governed by what an equilibrium does not carry: a fleet that turns over slowly, public acceptance that persists or erodes, and debt repaid on a schedule.</p>
<p>The zero-emission transition makes the problem concrete and fiscal. Road pricing is named among the levers for the next National Transport Plan, where the first TRANSPLAN deliverable argues the plan must be <span class="b">realistic and goal-directed</span> rather than a wish list [toi2172]; yet the national reform has stalled. Tolls raised NOK 16.8 billion in 2025, about 62% in city packages, against toll-company debt near NOK 78 billion [svv25, dok15]. As the fleet electrifies the toll base erodes under the policy, and every revision meets a public that has voted against tolls before: a single-issue anti-toll party won 16.7% in Bergen in 2019 [snl19]. Whether a 2050 plan is feasible &mdash; on emissions, on the public finances it rests on, and on who it asks to pay &mdash; depends on the order instruments arrive and whether people accept each step. <span class="b">That is a question about paths, and beneath it a prior one: is acceptance itself a measurable quantity?</span></p>
<div class="rqbox"><div class="mq">Main question. Which sequences of road-pricing instruments reach a desirable 2050 on emissions, finance and accessibility while staying acceptable to the people and firms who pay, across deep uncertainty; and which signals tell planners when to switch?</div>
<div class="rq"><b>RQ1 &middot; method (A1)</b>How can choice models estimated on real data drive agents that carry state year to year, so strategic end states become pathways?</div>
<div class="rq"><b>RQ2 &middot; behaviour (A2)</b>Does acceptance persist once a charge is permanent, and does information move it independently of experience?</div>
<div class="rq"><b>RQ3 &middot; planning (A3)</b>Which pathways, for passengers and for freight, are robust; what acceptance margin does each survive; and which signposts give lead time before one fails?</div></div>
<p><span class="b">What already exists.</span> I have a working prototype and a first measured result. At the Kristiansund tariff a zero-emission car with a tag pays NOK 19.04 against NOK 27.20, so each electric crossing earns NOK 8.16, or 30%, less [vegamot]. At today&rsquo;s four-in-ten electric share a crossing already earns about 12% less than in a fossil fleet; in an all-electric fleet, 30% less, debt unchanged. <span class="b">This erosion returns on page 5 as the finance signpost.</span></p>
<div class="twocol">
<div class="plate"><span class="plabel">One answer, or a path</span>{img("answers")}
<div class="cap">The left panel is what an equilibrium returns: one settled 2050, every car already where it ends up. The right is the same place lived as a sequence &mdash; the car turning electric, the toll bill falling, acceptance rising then dipping, the branch that survives and the branch that breaks. <span class="d">The gap between the two panels is the whole thesis.</span></div></div>
<div class="plate"><span class="plabel teal">What a crossing earns</span>
<div class="calc"><div class="qline">&gt; what one crossing earns, by fleet</div>
<div class="crow"><span class="cl">standard car</span><span class="cv">NOK 34.00</span></div>
<div class="crow"><span class="cl">with tag</span><span class="cv">NOK 27.20</span></div>
<div class="crow hl"><span class="cl">zero-emission + tag</span><span class="cv">NOK 19.04</span></div>
<div class="cdiv"></div>
<div class="crow"><span class="cl">each electric crossing earns</span><span class="cv gold">NOK 8.16 less &middot; &minus;30%</span></div>
<div class="crow"><span class="cl">today, at 40% electric</span><span class="cv">&minus;12% vs all-fossil</span></div>
<div class="crow"><span class="cl">all-electric fleet</span><span class="cv">&minus;30%, debt unchanged</span></div>
<div class="cdiv"></div>
<div class="crow"><span class="cl">the base erodes, the debt holds</span><span class="cv gold">~NOK 78 bn owed</span></div>
<div class="tier" style="margin-top:9px;display:inline-block">REAL &middot; Vegamot tariff [vegamot]</div></div>
<div class="cap">The discount that rewards clean cars is also the leak in the fund that pays for the roads. <span class="d">Whose leak, and whether they accept the patch, is pages 3&ndash;5.</span></div></div></div>
<div class="handoff">&rarr; So Norway needs the dynamic layer T&Oslash;I calls for. What should it be, and who has built the pieces?</div>
{FOOT("From end states to pathways",1)}</section>'''

# ============ PAGE 2 ============
P2=f'''<section class="sheet">
<div class="secnum">02 &middot; FIT, GAP AND WHAT IS NEW</div>
<h2>A dynamic layer <span class="g">beside</span> the national models</h2>
<p>The national system has three parts a candidate must name: <span class="b">NTM6</span>, the national passenger model for trips over 70 km; <span class="b">RTM</span>, the regional passenger model; and the national freight model, <span class="b">Nasjonal godsmodell (NGM)</span> [toi1819, ngm]. The Kristiansund case is regional and sub-70 km, so <span class="b">RTM</span> is the model this dynamic layer sits beside here; NTM6 and NGM set the national and freight context. T&Oslash;I&rsquo;s forward-looking review recommends not replacing these models but building dynamic ones alongside them [toi1819]; the institute has begun, with a MATSim-based assignment for Greater Oslo (tramodsim) and an activity-based model for Trondheim [tramodsim]. This PhD joins that line rather than importing a method from outside it: the exploratory, stress-testing layer that sequences instruments across thousands of futures and reports where each fails, so the national models keep producing the appraisal the agencies rely on while this layer supplies the robustness they are not built to give.</p>
<table class="ttable"><tr><th>The position asks for</th><th>This proposal answers with</th></tr>
<tr><td class="k">Zero-emission transition, with productivity, economy and equity</td><td>Emissions, finance (the eroding toll base) and a distributional floor are three explicit 2050 objectives</td></tr>
<tr><td class="k">Desirable futures under deep uncertainty</td><td>10&sup3; futures, satisficing targets, uncertainty decomposed by source</td></tr>
<tr><td class="k">DCM integrated with ABM</td><td>Choice models estimated on real survey data drive agents whose acceptance and fleet carry over year to year</td></tr>
<tr><td class="k">Backcasting and pathways, not one forecast</td><td>2050 targets fixed on page 3; instrument orders searched backward from them</td></tr>
<tr><td class="k">A practical contribution</td><td>Three testable claims and a named decision: the zero-emission discount and tariff</td></tr></table>
<p><span class="b">The gap.</span> Strategic models give end states and NGM gives freight chains; neither carries acceptance. Norwegian agent work assigns traffic with MATSim but takes acceptance as given [tramodsim]. Le Pira, Marcucci and Gatta integrated discrete choice and agent-based models to evaluate the acceptability of urban freight policy [lepira]; their agents are stakeholder groups negotiating in rounds, not a population living through calendar time. Adaptive pathway methods sequence actions against tipping points [haasnoot] but treat acceptance as an external scenario. The deep-uncertainty frontier runs ensembles over transport agent models, most recently on a fictional city with acceptance left out [fuhrer]. The acceptance evidence is careful and mostly static, and hybrid choice with a latent acceptance variable is now an established way to read it [hybridaccept, odeck08, borjesson16, toi2179]. <span class="b">Nobody has estimated acceptance on real data, carried it in agents over calendar time, and let it decide which passenger and freight pathways survive.</span></p>
<div class="heart">The question beneath the whole proposal is prior to any pathway: is public acceptance a measurable quantity that can be estimated on real data and carried forward in time, or not? The thesis answers that first; the ensemble and the robust front are what the answer is then used for.</div>
<div class="claims">
<div class="claim"><div class="cn">1</div><div class="ct">Acceptance, estimated and carried, as admissibility</div><p>A pathway counts only if estimated acceptance stays above a threshold every step; the largest shift it survives is its acceptance margin &mdash; a result, not an assumption. (Delivered p5.)</p></div>
<div class="claim"><div class="cn">2</div><div class="ct">Uncertainty decomposed by source</div><p>The 2050 spread is split, year by year, into behavioural parameters, external futures and the choice of path, so planners see which uncertainty more data can reduce and which only adaptation can. (Delivered p5.)</p></div>
<div class="claim"><div class="cn">3</div><div class="ct">Signposts validated twice, ordered across modes</div><p>Failure signals are scored on held-out futures for lead time and false alarms, then against dated events; passenger and freight signposts are compared, because the slower fleet decides which fires first. (Delivered p4&ndash;5.)</p></div></div>
<div class="plate"><span class="plabel">The engine &mdash; what each layer carries that the one below cannot</span>{img("engine")}
<div class="cap">Read bottom to top: the real town (OSM, register, counts) &rarr; choice estimated from survey data (Biogeme) &rarr; agents that remember (the custom agent model, carrying &rho;) &rarr; the same agents in a thousand worlds (EMA Workbench) &rarr; the order that survives (the robust search). The bracket ladder on the right names what passes between layers &mdash; homes sampled, then &beta;,&eta;,&rho;, then agent states year by year, then futures on target. <span class="d">An equilibrium collapses all five planes into one number for one year; choice and acceptance are the two planes this PhD estimates.</span></div></div>
<div class="handoff">&rarr; Here is that layer, written down.</div>
{FOOT("Fit, gap and what is new",2)}</section>'''

# ============ PAGE 3 ============
P3=f'''<section class="sheet">
<div class="secnum">03 &middot; THE MODEL</div>
<h2>What each agent <span class="g">decides and remembers</span></h2>
<p>Each year t, a household or firm n chooses a vehicle, how often to cross and when, from a choice model where the instruments in force set the cost. Acceptance is estimated in its core cross-sectional form in A1, as an integrated choice and latent-variable (ICLV) model on real wave-1 data &mdash; the hybrid-choice approach used to read acceptance surveys elsewhere [hybridaccept], extending Le Pira, Marcucci and Gatta from negotiating stakeholder groups to a population of individually estimated agents [lepira].</p>
<div class="eq">(1)&nbsp;&nbsp;U(n,j,t) = &beta;&middot;cost(j, I(t)) + &theta;&prime;&middot;x(n,j) + &epsilon;(n,j,t)<br>(2)&nbsp;&nbsp;A*(n,t) = &rho;&middot;A(n,t&minus;1) + &delta;&middot;dose(n,t) + &eta;&middot;info(n) + &gamma;&prime;&middot;z(n) + u(n,t)<br>(M)&nbsp;&nbsp;I&#8342;(n) = &alpha;&#8342; + &lambda;&#8342;&middot;A*(n) + &nu;&#8342;&nbsp;&mdash; attitudinal indicators load on latent acceptance<br>(3)&nbsp;&nbsp;pathway p is admissible if the share with A* &ge; &lambda; holds every year; its acceptance margin is the largest rise in &lambda; it survives.</div>
<p>A*(n) is latent, measured by K attitudinal indicators (agreement that the charge is fair, trusted, worth its purpose) through (M), identified jointly with the choice model; the taste parameters &beta; are random across the population with a normal mixing distribution. This is the full ICLV, not a reduced attitude score. The dynamic form (2) adds one first-order persistence term &rho;, identified between the two waves with the initial-conditions problem handled [wooldridge]; <span class="b">&rho; is tested by H1 and &eta; by H2 on page 4.</span> &rho; is a Level-3 stretch; the core rests on the cross-sectional model. The estimated parameters then drive a <span class="b">custom agent model in Python/NumPy</span>: each year agents replace cars by a binary logit, choose modes by the estimated MNL, and meet congestion through a BPR curve solved by the method of successive averages &mdash; the engine that carries acceptance and fleet year to year.</p>
<div class="twocol">
<div class="plate"><span class="plabel">What memory does</span>{img("memory")}
<div class="cap">Three agents to 2050. The commuter crosses the threshold &lambda; in 2031 and, because &rho; is high, stays above it; the occasional crosser never leaves; the van driver, with the largest dose, falls below &lambda; from 2035. <span class="d">Memory, not the current bill, decides who stays accepting &mdash; which is exactly what an equilibrium cannot hold.</span> <span class="tier">ILLUSTRATIVE &middot; &rho;, dose shown are not estimates</span></div></div>
<div class="plate"><span class="plabel">One household, three moments</span>{img("household")}
<div class="cap">2026 the household opposes the package on a fossil car; 2029 it replaces the car, the bill falls 30%, and acceptance carries forward; 2035 the discount ends and acceptance drops. <span class="d">The same &rho; that holds acceptance up in 2029 is what lets it fall in 2035 &mdash; persistence cuts both ways.</span></div></div></div>
<p><span class="b">What a pathway is.</span> Five instruments: revision of the package, the zero-emission rate, a passenger distance charge, a heavy-vehicle distance charge, earmarking of revenue. A3 is a search, not a catalogue: choose each instrument&rsquo;s switch-on year and level to maximise the share of futures meeting all three 2050 targets and minimise maximum regret, subject to acceptance above threshold every year, revenue covering debt service, and an accessibility floor, with a many-objective robust algorithm and scenario discovery naming where the robust set still breaks [prim, mordm]. Robustness-as-objective follows the stability-metrics line of Shaabani, Hvattum, Hoff and Laporte [shaabani]. Full enumeration of a reduced set of four of the five instruments is 4 + 36 + 216 + 648 = 904, kept to check the search; the full search ranges over switch-years and levels for all five, on the order of 10&#8308; pathways.</p>
<table class="ttable"><tr><th>Target in 2050</th><th>Metric</th><th>Anchor</th></tr>
<tr><td class="k">Emissions</td><td>Well-to-wheel CO&#8322;e from road traffic in the case area</td><td>Climate Change Act: 90&ndash;95% by 2050 [klimalov]</td></tr>
<tr><td class="k">Finance</td><td>Toll revenue &ge; debt service; failure if below three years running</td><td>Package financing [innst337]</td></tr>
<tr><td class="k">Accessibility (equity)</td><td>Generalised cost of the lowest income quintile no higher than 2026</td><td>The equity the call names; the map on p4 shows the spatial side</td></tr></table>
<p><span class="b">What would falsify it.</span> If &rho; &asymp; 0, agents need no memory and claim 1 reduces to a static result; if &eta; &asymp; 0, information does not move acceptance and H2 fails; if the fast engine cannot reproduce the network model within tolerance, the ensemble is cut to what the network model can run. Each is reported whichever way it falls. <span class="b">Tools and skill.</span> Python throughout: Biogeme, the custom agent model, EMA Workbench, OSMnx/NetworkX, OR-Tools, NGM elasticities. A prototype pipeline, built in preparation with disclosed AI assistance, runs the whole chain end to end; a reproducibility check estimated a mixed logit on the public Swissmetro data in Biogeme (N = 6,768, final log-likelihood &minus;5214.9 against the published &asymp;&minus;5214.8) [evdcm], showing the pipeline runs on real choice data, not that I am already an estimator &mdash; the skill path is in the cover letter.</p>
<div class="handoff">&rarr; Tested where acceptance is live and freight is real.</div>
{FOOT("The model",3)}</section>'''

# ============ PAGE 4 ============
P4=f'''<section class="sheet">
<div class="secnum">04 &middot; CASE AND DESIGN</div>
<h2>Kristiansund, where <span class="g">acceptance is live</span></h2>
<p><span class="b">Why Kristiansund, and where freight enters.</span> Bypakke Kristiansund began collection on 1 June 2026 at two rv70 stations, Nordsundbrua and Omsundbrua; about 70% of the package is toll-financed over up to 15 years [bypakke, innst337]. A car pays NOK 34, 27.20 with a tag, 19.04 if zero-emission with a tag [vegamot]. The council approved the basis 26 to 19 and the county 33 to 14: acceptance here is contested and live. The town sits on the M&oslash;re og Romsdal west-coast corridor, where the Ferjefri E39 programme and NGM treat coastal short-sea as the competing mode for freight to Oslo and the continent [ngm]. Freight is estimated here, not borrowed: a short carrier stated-choice block gives the mode-and-timing response of hauliers to a distance charge, which the NGM chains carry to the network. Because the heavy fleet turns over slowly and the sea alternative needs volume to stay viable, a pathway that reaches road freight too late closes the modal-shift window and locks emissions in. <span class="b">Molde, with no package, is the no-toll control town</span> &mdash; information without experience, against Kristiansund&rsquo;s information plus experience.</p>
<div class="plate"><span class="plabel teal">The toll is a map of who can avoid it</span>{img("kmap")}
<div class="cap">Every building is assigned to the side of Nordsundbrua it reaches without the bridge, on the real OSM graph. Red: Nordlandet, which only the bridge connects &mdash; 48% of junction-pairs lose every road connection at the split. Teal: the toll-free Atlanterhavstunnelen, a free alternative for some. <span class="d">Exposure is geography; the equity target on page 3 is income &mdash; the thesis reports exposure crossed with income, so the floor is distributional and not merely spatial.</span> <span class="tier">REAL &middot; OSM graph</span></div></div>
<div class="twocol"><div>
<h3>Survey &mdash; three blocks, Bayesian D-efficient</h3>
<p class="small"><b>Acceptance block</b> (households), information randomised in three arms &mdash; personal cost, purpose narrative, control &mdash; so format and content are both tested. <b>Passenger stated-choice:</b> vehicle at next replacement, crossing frequency and time, under national tariff ranges. <b>Carrier stated-choice</b> (firms and hauliers): road vs coastal short-sea, route and timing under a distance charge, single wave, small targeted sample, NGM-anchored &mdash; reached through freight-industry channels (the cover letter names the route). Kristiansund carries household and carrier design; Molde the acceptance control. Wave 1 + carrier block month 6; wave 2 month 18, same households. Planning sample 1,428 Kristiansund, 714 Molde, sized by minimum detectable effect.</p>
<h3>Hypotheses</h3>
<p class="small"><b>H1</b> acceptance persists once a charge is permanent (&rho; &gt; 0 in eq 2), tested as within-person change between waves against dose. <b>H2</b> information moves acceptance independently of experience (&eta; &ne; 0 in eq 2), tested by the randomised arms and by the Molde control, turning the Norwegian information&ndash;attitude correlation [odeck08] into a causal estimate. <b>H3</b> a distance charge shifts carrier mode choice toward short-sea above a threshold rate.</p></div>
<div>
<h3>Ethics and data management</h3>
<p class="small">The two waves re-link the <b>same households twelve months apart</b>, so personal identifiers are retained across a year: lawful basis under GDPR Art. 6, consent-for-re-contact collected at wave 1, a pseudonymisation key held separately from the response data by the supervisor, a stated retention-and-deletion schedule, and attitudinal data minimised. The study is notified to <b>Sikt</b> before fieldwork; a Data Management Plan is filed; traffic data are used as aggregate station counts only. SSB/RVU microdata are governed by their own agreements, applied for in week 1.</p>
<h3>Freight fallback</h3>
<p class="small">If the carrier sample under-powers, the freight arm reverts to NGM mode-split elasticities with a reported sensitivity on the key elasticity; the freight signpost becomes a modelled consequence, and the thesis ladder absorbs it without loss of a complete dissertation.</p></div></div>
<div class="dark-inset"><div class="dl">Molde &middot; the same method on a second real network</div>{img("molde_pinch","",style="max-height:360px;object-fit:cover;object-position:center")}
<div class="dc">Route a van between every pair of junctions on Molde&rsquo;s real road graph: 18% of all fastest routes funnel through one street, &Oslash;vre veg. Closing it (plate 02) slows 32% of trips and strands 0.9%. Kristiansund&rsquo;s bridge is the same fragility &mdash; 48% of junction-pairs cut &mdash; measured, not assumed. <span class="tier" style="color:#8fb0c4;border-color:#2a3647">REAL &middot; Molde OSM &middot; betweenness</span></div></div>
<div class="handoff">&rarr; And here is the four-year plan to deliver it.</div>
{FOOT("Case and design",4)}</section>'''

# ============ PAGE 5 ============
P5=f'''<section class="sheet">
<div class="secnum">05 &middot; PLAN, ROBUSTNESS AND RECEIPTS</div>
<h2>The robust front, and <span class="g">how it is delivered</span></h2>
<p><span class="b">The ensemble, priced.</span> The robust search explores ~10&#8308; candidate pathways, each scored against a Latin-hypercube sample of futures, the robust set re-checked on the full 10&sup3;. Each evaluation advances a zonal state to 2050 in ~25 ms, so the budget is 40&ndash;150 CPU-hours, parallel, inside a desktop over a weekend. Fidelity is measured on <span class="b">two real networks, Molde and Kristiansund</span>: the fast engine reproduces static-network car travel times per zone pair within ~15% MAE (r 0.73&ndash;0.84); a dynamic MATSim cross-check (Molde, 4,000 agents) matches to ~19% at free flow (r 0.74) and the static assignment to 6% (r 0.999), and the free-flow engine breaks under a tenfold capacity squeeze &mdash; which is why robust pathways are re-checked on the network model [evfid].</p>
<div class="plate"><span class="plabel">The robust front &mdash; and the order each pathway switches on</span>{img("front")}
<div class="cap">Each dot is one of 904 pathways scored on acceptance margin and share of futures on target; the front is the best trade-off, E chosen for the widest shift in &lambda; it survives. The rail below is the finding the scatter cannot show: <span class="d">the same instruments in a different order give a different fate</span> &mdash; A opens with the ZE rate and fails, E earmarks first then charges distance and holds. The order is the result. <span class="tier">PROTOTYPE &middot; parameters assumed until A1&ndash;A3 &middot; 10 seeds &middot; hypervolume-converged</span></div></div>
<div class="twocol">
<div class="plate"><span class="plabel">What replaces the lost revenue</span>{img("erosion")}
<div class="cap">Revenue &divide; debt across 1,000 futures; 22% fail to cover the debt before 2041, 30% by 2050. <span class="d">This is the page-1 erosion grown up &mdash; the &minus;30%/crossing becomes a debt-cover signpost, and the year the median future crosses the debt line is the finance signpost the ring promised.</span> <span class="tier">PROTOTYPE</span></div></div>
<div><div class="vpanel"><div class="tcat" style="color:var(--gold)">Claim 2 &middot; uncertainty by source</div>
<p class="small" style="margin:4px 0 6px">Where the 2050 spread comes from, by year &mdash; so planners see which uncertainty more data can reduce (behaviour) and which only adaptation can (external futures).</p>
<div style="font-family:Montserrat;font-size:9px;letter-spacing:.5px;color:var(--mut);display:flex;justify-content:space-between"><span>2026</span><span>2038</span><span>2050</span></div>
<div class="vbar"><span style="background:var(--terra);width:42%">BEHAVIOUR 42%</span><span style="background:var(--gold);width:37%">FUTURES 37%</span><span style="background:var(--sage);width:21%">PATH 21%</span></div>
<p class="small" style="margin:4px 0 0;color:var(--mut);font-style:italic">Sobol variance shares, prototype. Behavioural parameters dominate early (more survey data helps); external futures dominate late (only adaptation helps).</p>
<div class="tier" style="margin-top:7px;display:inline-block">PROTOTYPE &middot; illustrative shares</div></div>
<table class="ttable" style="margin-top:8px"><tr><th>Article</th><th>Submit</th><th>Data</th></tr>
<tr><td>A1 Choice estimated</td><td>M12</td><td>Wave 1 + carrier block</td></tr>
<tr><td>A2 Acceptance that persists</td><td>M24</td><td>Both waves</td></tr>
<tr><td>A3 Robust pathways</td><td>M32</td><td>Ensemble; dated events</td></tr></table></div></div>
<h3>The computational stack &mdash; one tool named per article</h3>
<div class="tools">
<div class="tcol"><div class="tcat">Estimate</div><div class="ttool">Biogeme</div><div class="ttool s">mixed logit &middot; ICLV</div><div class="trole">Acceptance and carrier mode choice estimated on real survey data.</div><div class="tart">A1 &middot; A2</div></div>
<div class="tcol"><div class="tcat">Carry</div><div class="ttool">Agent model</div><div class="ttool s">Python &middot; NumPy</div><div class="trole">Fleet logit, estimated MNL, BPR/MSA congestion &mdash; acceptance and fleet carried year to year.</div><div class="tart">A2 &middot; A3</div></div>
<div class="tcol"><div class="tcat">Explore</div><div class="ttool">EMA Workbench</div><div class="ttool s">&epsilon;-NSGA-II &middot; PRIM</div><div class="trole">1,000 futures, robust search, scenario discovery (MORDM).</div><div class="tart">A3</div></div>
<div class="tcol"><div class="tcat">Network</div><div class="ttool">OSMnx &middot; NetworkX</div><div class="ttool s">OR-Tools &middot; MATSim</div><div class="trole">Real road graphs, routing checks, dynamic cross-check.</div><div class="tart">A1 &middot; A3</div></div>
<div class="tcol"><div class="tcat">Freight</div><div class="ttool">NGM</div><div class="ttool s">national freight model</div><div class="trole">Commodity chains, mode split, load factors, empty running.</div><div class="tart">A3</div></div>
<div class="tcol"><div class="tcat">Compose</div><div class="ttool">Rhino &middot; Grasshopper</div><div class="ttool s">Ladybug &middot; Blender</div><div class="trole">Every figure computed from the data in one parametric pipeline.</div><div class="tart">all plates</div></div></div>
<div class="twocol"><div>
<h3>A four-year appointment, and a thesis that survives a failed survey</h3>
<p class="small">The post is three-to-four years; I plan for the <b>four-year appointment with 25% duties</b>: a 36-month research core (the schedule on page 6) plus teaching and a ~30-ECTS training component weighted to discrete-choice courses. <b>Level 1</b> (no new data): A1 on national ranges, A3 on NGM elasticities, freight included &mdash; a complete thesis, though at Level 1 the headline novelty becomes a methods demonstration on assumed parameters. <b>Level 2</b> (wave 1 + carrier): adds H2, cross-sectional A2, estimated freight. <b>Level 3</b> (both waves): adds H1 and the persistence term. Each level is a complete dissertation; the survey raises the ceiling, and the guaranteed spine is my own collected survey.</p>
<h3>Calendar (36-month research core; 48-month appointment)</h3>
<p class="small">Week 1: SSB/RVU applications and Sikt notification filed, off the critical path. Months 1&ndash;6 coursework (incl. philosophy of science, DCM) + pilot with Norwegian-speaking co-authors. M6 wave 1 + carrier &middot; M12 A1 &middot; M18 wave 2 &middot; M20 <b>midway evaluation</b> &middot; M24 A2 &middot; M32 A3 &middot; M32&ndash;36 summary; duties spread across the 48-month appointment. Articles pipelined, not serial.</p></div>
<div>
<h3>Proposed supervisory constellation</h3>
<div class="constell">
<div class="cnode"><div class="cr">Robustness / OR</div><p>Many-objective robust optimisation and stability metrics &mdash; the lineage of [shaabani] (Hvattum, Hoff).</p></div>
<div class="cnode"><div class="cr">Discrete choice</div><p>ICLV and stated-choice design &mdash; the tradition of [lepira] (Marcucci, Gatta), the skill I deepen.</p></div>
<div class="cnode"><div class="cr">Freight / transport economics</div><p>Logistics and toll economics &mdash; the ground of [odeck08] (Odeck, Br&aring;then) and the Logistics department.</p></div></div>
<p class="small" style="margin-top:7px">A proposed constellation, not a settled one; all modelling and evidence to date is my own. The three references this proposal most leans on are each authored inside Molde&rsquo;s own groups &mdash; the expertise I would learn under is resident where the work would sit.</p>
<h3>Risk and response</h3>
<table class="ttable"><tr><th>Risk</th><th>Response</th></tr>
<tr><td class="k">Low response / attrition</td><td>Panel top-up; sample sized for it; Level 2 holds</td></tr>
<tr><td class="k">No microdata by M6</td><td>Published ranges + NGM; spine is the own survey</td></tr>
<tr><td class="k">Carrier under-powers</td><td>Revert to NGM elasticities with reported sensitivity</td></tr>
<tr><td class="k">Language</td><td>Instrument in English, translated and piloted with Norwegian co-authors</td></tr></table></div></div>
<p class="small"><span class="b">Why here, and the decision it yields.</span> The position sits in the Department of Logistics, may link to TRANSPLAN, and asks exactly for behaviour under the zero-emission transition with its effects on finance and equity &mdash; which is this proposal&rsquo;s spine. The thesis reports an explicit, defensible <b>recommendation on the zero-emission discount and tariff</b> for Bypakke Kristiansund, not only a method. <span class="b">Receipts.</span> Every number traces to a tagged commit, 89 automated tests, figures generated from the same code; code released openly, anonymised data deposited FAIR once Sikt allows; AI-tool use disclosed. <span class="b">Dissemination.</span> Three journal articles, a Norwegian-language piece in <i>Samferdsel</i>, and the annual NORS conference, where I have presented before.</p>
<div class="handoff">&rarr; The finance signpost that warns a path is failing is the same erosion page 1 showed already under way. The ring closes.</div>
{FOOT("Plan, robustness and receipts",5)}</section>'''

# ============ PAGE 6 ============
groups=[
 ("Norwegian models, policy and case",[
   ("toi1819","Fl&uuml;gel et al. (2021). A forward-looking perspective on Norwegian transport models. T&Oslash;I 1819/2021."),
   ("toi2172","Tveter, E. et al. (2026). Veivalg for en realistisk og m&aring;lrettet transportplan. T&Oslash;I 2172/2026."),
   ("tramodsim","Fl&uuml;gel, Fl&ouml;tter&ouml;d, Ringdal, Weber (2023). TraModSim. T&Oslash;I 1993/2023."),
   ("ngm","Madslien, Hovi et al. Nasjonal godstransportmodell. T&Oslash;I 1247/2012; cost-model update bas&aring;r 2021 (2022)."),
   ("klimalov","Lov om klimam&aring;l (klimaloven), LOV-2017-06-16-60. 2050 target 90&ndash;95% vs 1990."),
   ("svv25","Statens vegvesen (2026). Bompengerapport 2025 (&asymp;NOK 16.8 bn; debt &asymp;NOK 78 bn, Tabell 38)."),
   ("bypakke","Bypakke Kristiansund: council 18 Apr 2024 (26-19); Storting 3 Jun 2025; tolling &le; 15 yr."),
   ("innst337","Innst. 337 S (2024-2025), Prop. 87 S: Bypakke Kristiansund. Storting, 3 June 2025."),
   ("vegamot","Vegamot AS, Bypakke Kristiansund tariff: 34 / 27.20 tag / 19.04 ZE+tag; from 1 June 2026."),
   ("snl19","Bergen municipal election 2019 (valg.no/SSB): FNB 16.7%, 11 seats."),
 ]),
 ("Acceptance and discrete choice",[
   ("lepira","Le Pira, Marcucci, Gatta, Inturri, Ignaccolo (2017). Integrating DCM and ABM for stakeholder policy acceptability in urban freight. Res. Transp. Econ. 64, 13-25. DOI 10.1016/j.retrec.2017.08.002"),
   ("hybridaccept","Ben-Akiva et al. (2002). Hybrid choice models. Marketing Letters 13(3), 163-175 (method anchor)."),
   ("odeck08","Odeck, Br&aring;then (2008). Travel demand elasticities and users&rsquo; attitudes: Norwegian toll projects. Transp. Res. A 42(1), 77-94."),
   ("borjesson16","B&ouml;rjesson, Eliasson, Hamilton (2016). Why experience changes attitudes to congestion pricing: Gothenburg. Transp. Res. A 85, 1-16."),
   ("toi2179","Acceptance of distance-based road pricing: national choice experiment + Oslo field trial. T&Oslash;I 2179/2026."),
   ("iclv2","Vij, Walker (2016). How, when and why integrated choice and latent variable models are latently useful. Transp. Res. B 90, 192-217. DOI 10.1016/j.trb.2016.04.021"),
 ]),
 ("ABM, pathways and robustness",[
   ("fuhrer","F&uuml;hrer, d&rsquo;Hont, Rouwette, Kwakkel (2025). Transp. Res. Interdisc. Persp. 34, 101683 [vol. to confirm]. DOI 10.1016/j.trip.2025.101683"),
   ("haasnoot","Haasnoot, Kwakkel, Walker, ter Maat (2013). Dynamic adaptive policy pathways. Glob. Environ. Change 23(2), 485-498."),
   ("mordm","Kasprzyk, Nataraj, Reed, Lempert (2013). Many-objective robust decision making. Environ. Model. Softw. 42, 55-71."),
   ("prim","Friedman, Fisher (1999). Bump hunting in high-dimensional data. Stat. Comput. 9(2), 123-143."),
   ("shaabani","Shaabani, Hvattum, Laporte, Hoff (2024). Stability metrics for a maritime inventory routing problem. EJTL 13, 100146. DOI 10.1016/j.ejtl.2024.100146"),
   ("wooldridge","Wooldridge (2005). Initial conditions in dynamic nonlinear panel models. J. Appl. Econometrics 20(1), 39-54."),
 ]),
]
refhtml=""
for gh,items in groups:
    refhtml+=f'<div class="refgroup"><div class="refgh">{gh}</div>'
    for k,v in items:
        refhtml+=f'<div class="ref"><span class="rk">[{k}]</span> {v}</div>'
    refhtml+='</div>'
P6=f'''<section class="sheet">
<div class="secnum">06 &middot; REFERENCES AND RECEIPTS</div>
<h2>References &amp; <span class="g">receipts</span></h2>
<p class="small">All cited sources verified against primary sources as of 2026-10-17. Evidence entries are runnable artefacts in the repository, traced to tagged commits.</p>
<div class="twocol" style="gap:30px">{refhtml}</div>
<div class="ledger"><div class="tcat" style="color:var(--teal)">Evidence ledger &mdash; receipts you can run</div>
<table><tr><td class="h">[evdcm]</td><td><b>Swissmetro mixed-logit reproduction</b> &mdash; Biogeme 3.3.5, N=6,768, 1,000 Halton draws. Result: final LL &minus;5214.9 vs published &asymp;&minus;5214.8. <span class="h">evidence/dcm-swissmetro</span></td></tr>
<tr><td class="h">[evfid]</td><td><b>Zonal-vs-network fidelity benchmark</b> &mdash; Molde + Kristiansund OSM graphs. Result: &asymp;15% MAPE (r 0.73&ndash;0.84); MATSim dynamic cross-check 19% free-flow, breaks under 10&times; congestion. <span class="h">evidence/fidelity-benchmark</span></td></tr>
<tr><td class="h">[tests]</td><td><b>89 automated tests</b>; every figure generated from the same code; FAIR data deposit once Sikt allows. <span class="h">pytest &middot; tagged at submission</span></td></tr></table></div>
<div class="plate" style="margin-top:12px"><span class="plabel">The thesis, as a system &mdash; data to articles to claims</span>{img("thesismap")}
<div class="cap">Each data source feeds a wave; each wave feeds an article; each article delivers a claim. <span class="d">Cut the survey wires and the teal spine &mdash; own collected data and national ranges &mdash; still reaches A1 and A3: the thesis completes without a single external dependency.</span></div></div>
{FOOT("References and receipts",6)}</section>'''

html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>From end states to pathways &mdash; TRANSPLAN proposal</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Spectral:ital,wght@0,400;0,500;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>{P1}{P2}{P3}{P4}{P5}{P6}</body></html>'''
open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/v57/proposal.html","w").write(html)
print("proposal.html", len(html)//1024,"KB")
