# -*- coding: utf-8 -*-
import json
D=json.load(open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/v57/plates_data.json"))
def img(k,style=""): return f'<img src="{D[k]}" style="{style}">'
CSS=open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/v57/_css58.txt").read()
FOOT=lambda t,n:f'<div class="foot"><span>Arshad Akhtar Abbasia</span><span>{t}</span><span class="r">github.com/Astheno-sphere/computational_logistics &middot; {n} / 6</span></div>'

P1=f'''<section class="sheet">
<div class="kick">Research proposal &middot; Department of Logistics &middot; Molde University College</div>
<div class="doctitle">From end states to <span class="g">pathways</span></div>
<div class="docsub">Estimating acceptance, carrying it in agents, and finding robust road-pricing paths to a low-carbon Norway in 2050</div>
<div class="contrib">No one has estimated road-pricing acceptance on real data, carried it in agents through the years, and let it decide which passenger and freight pathways survive. This thesis is the first to do it. <span class="methods">Discrete choice (DCM) &rarr; agents with memory (ABM) &rarr; robust pathways under deep uncertainty (MORDM).</span></div>
<div class="startband"><div class="sbt">The engine already runs.</div><div class="sbb">A public repository, 89 automated tests, the Swissmetro choice model reproduced, two real Norwegian road networks benchmarked. Most PhDs build this in year one. Mine is built and tested before day one. <span class="sbrepo">github.com/Astheno-sphere/computational_logistics</span></div></div>
<div class="hr"></div>
<div class="secnum">01 &middot; THE PROBLEM</div>
<h2>What an equilibrium <span class="g">cannot carry</span></h2>
<p>Norway appraises transport with a national model that solves one equilibrium for one year. Ask it what 2050 looks like under a set of assumptions, and it answers with care. Ask it how the country gets there, and which routes fail on the way, and it has nothing to say. It was not built for that. T&Oslash;I&rsquo;s own review agrees: the current models are static and macroscopic [toi1819]. The path to 2050 turns on what an equilibrium cannot hold. A car fleet that turns over slowly. Public acceptance that lasts or fades. Debt that comes due on a schedule.</p>
<p>The zero-emission transition makes this concrete, and fiscal. Road pricing is one of the levers named for the next National Transport Plan, where the first TRANSPLAN report says the plan must be realistic, not a wish list [toi2172]. Yet the national reform has stalled. Tolls raised NOK 16.8 billion in 2025, about 62 percent of it in city packages, against toll-company debt near NOK 78 billion [svv25]. As cars go electric, the toll base erodes under the very policy that rewards them. And every revision meets a public that has voted against tolls before. In Bergen in 2019 a single-issue anti-toll party won 16.7 percent [snl19]. Whether a 2050 plan can work turns on three things: emissions, the public finances it rests on, and who it asks to pay. What decides it is the order the instruments arrive in, and whether people accept each step.</p>
<div class="rqbox"><div class="mq">Main question. Which sequences of road-pricing instruments reach a good 2050 on emissions, finance and access while staying acceptable to the people and firms who pay, across deep uncertainty; and which signals tell planners when to switch?</div>
<div class="rq"><b>RQ1 &middot; method (A1)</b>Can a choice model built from real survey data drive agents that remember, so one 2050 end-state becomes a year-by-year path?</div>
<div class="rq"><b>RQ2 &middot; behaviour (A2)</b>Does acceptance last once a charge is permanent, and can information move it on its own?</div>
<div class="rq"><b>RQ3 &middot; planning (A3)</b>Which pathways, for passengers and for freight, stay robust; what acceptance margin does each survive; and which signposts warn before one fails?</div></div>
<p><span class="b">A first measured result.</span> At the Kristiansund tariff a zero-emission car with a tag pays NOK 19.04 instead of NOK 27.20. Each electric crossing earns NOK 8.16 less, a cut of 30 percent [vegamot]. Four in ten cars are already electric, so a crossing today earns about 12 percent less than it would in a fossil fleet. In an all-electric fleet it earns 30 percent less, and the debt does not move. This erosion returns on page 5 as the finance signpost. And the thesis finishes even if no survey or microdata ever arrives: the spine is my own data and published national ranges, as the ladder on page 5 shows.</p>
<div class="twocol">
<div class="plate"><span class="plabel">One answer, or a path</span>{img("answers")}
<div class="cap">The left panel is what an equilibrium gives you: one settled 2050, every car already where it ends up. The right is the same town lived forward. The car turns electric. The toll bill falls. Acceptance rises, then dips. One branch survives, one breaks. <span class="d">The gap between the two panels is the whole thesis.</span></div></div>
<div class="plate"><span class="plabel teal">What a crossing earns</span>
<div class="calc"><div class="qline">&gt; what one crossing earns, by fleet</div>
<div class="crow"><span class="cl">standard car</span><span class="cv">NOK 34.00</span></div>
<div class="crow"><span class="cl">with tag</span><span class="cv">NOK 27.20</span></div>
<div class="crow hl"><span class="cl">zero-emission + tag</span><span class="cv">NOK 19.04</span></div>
<div class="cdiv"></div>
<div class="crow"><span class="cl">each electric crossing earns</span><span class="cv gold">NOK 8.16 less, &minus;30%</span></div>
<div class="crow"><span class="cl">today, at 40% electric</span><span class="cv">&minus;12% vs all-fossil</span></div>
<div class="crow"><span class="cl">all-electric fleet</span><span class="cv">&minus;30%, debt unchanged</span></div>
<div class="cdiv"></div>
<div class="crow"><span class="cl">the base erodes, the debt holds</span><span class="cv gold">~NOK 78 bn owed</span></div></div>
<div class="tier" style="margin-top:9px;display:inline-block">REAL &middot; Vegamot tariff [vegamot]</div>
<div class="cap">The discount that rewards clean cars is also the leak in the fund that pays for the roads. <span class="d">Who leaks, and whether they accept the patch, is pages 3 to 5.</span></div></div></div>
<div class="handoff">&rarr; So Norway needs the dynamic layer T&Oslash;I calls for. What is it, and who has built the pieces?</div>
{FOOT("From end states to pathways",1)}</section>'''

P2=f'''<section class="sheet">
<div class="secnum">02 &middot; FIT, GAP AND WHAT IS NEW</div>
<h2>A dynamic layer <span class="g">beside</span> the national models</h2>
<p>The national system has three parts a candidate must know. NTM6 is the national passenger model for trips over 70 km. RTM is the regional one. NGM is the national freight model [toi1819, ngm]. Kristiansund is a regional, sub-70 km case, so RTM is the model this layer sits beside here; NTM6 and NGM set the national and freight context. T&Oslash;I&rsquo;s own review asks for exactly this. Not to replace these models, but to build dynamic ones next to them [toi1819]. The institute has started, with a MATSim assignment for Oslo and an activity model for Trondheim [tramodsim]. This PhD joins that line. It adds the layer that stress-tests instruments across thousands of futures and reports where each one fails, so the national models keep giving the agencies their appraisal while this layer gives the robustness they were never built for.</p>
<table class="ttable"><tr><th>The position asks for</th><th>This proposal answers with</th></tr>
<tr><td class="k">The zero-emission transition, with its effect on finance and equity</td><td>Emissions, the eroding toll base, and a distributional floor are three explicit 2050 targets</td></tr>
<tr><td class="k">Behaviour under deep uncertainty</td><td>1,000 futures, satisficing targets, uncertainty split by source</td></tr>
<tr><td class="k">DCM joined to ABM</td><td>Choice models from real survey data drive agents whose acceptance and fleet carry over year to year</td></tr>
<tr><td class="k">Backcasting, not one forecast</td><td>2050 targets fixed on page 3; instrument orders searched backward from them</td></tr>
<tr><td class="k">A practical contribution</td><td>Three testable claims, and a named decision on the zero-emission discount and tariff</td></tr></table>
<p><span class="b">The gap.</span> Strategic models give end-states. NGM gives freight chains. Neither carries acceptance. Norwegian agent work assigns traffic with MATSim but takes acceptance as given [tramodsim]. Le Pira, Marcucci and Gatta put discrete choice and agent models together to test the acceptability of urban freight policy [lepira], but their agents are stakeholder groups bargaining in rounds, not a population living through the years. Adaptive-pathway methods sequence actions against tipping points [haasnoot], but treat acceptance as an outside scenario. The deep-uncertainty frontier runs ensembles over agent models, most recently on a made-up city with acceptance left out [fuhrer]. The acceptance evidence itself is careful, and mostly static [hybridaccept, odeck08, borjesson16, toi2179].</p>
<div class="heart">So the contribution is one line. No one has estimated acceptance on real data, carried it in agents through calendar time, and let it decide which passenger and freight pathways survive. The prior question is simpler still: is acceptance even measurable? The thesis answers that first. Everything else is what the answer is used for.</div>
<div class="claims">
<div class="claim"><div class="cn">1</div><div class="ct">Acceptance, estimated and carried</div><p>A pathway counts only if estimated acceptance stays above a line every year. The biggest shift it survives is its acceptance margin. A result, not an assumption. (Page 5.)</p></div>
<div class="claim"><div class="cn">2</div><div class="ct">Uncertainty split by source</div><p>The 2050 spread is split, year by year, into behaviour, outside futures, and the choice of path. Planners see which uncertainty more data can cut, and which only adaptation can. (Page 5.)</p></div>
<div class="claim"><div class="cn">3</div><div class="ct">Signposts, tested twice, ordered across modes</div><p>Warning signals are scored on held-out futures, then against events that happened. Passenger and freight signposts are compared, because the slower fleet decides which fires first. (Pages 4 to 5.)</p></div></div>
<div class="plate"><span class="plabel">The engine, and what each layer carries</span>{img("engine")}
<div class="cap">Read it bottom to top. The real town (OSM, register, counts). Choice estimated from survey data (Biogeme). Agents that remember, carrying acceptance through &rho; (the custom agent model). The same agents in a thousand futures (EMA Workbench). The order that survives (the robust search). <span class="d">Freight rides all five: carrier choice is estimated too, heavy vehicles carry their own fleet and load factors, and freight pathways are searched beside passenger ones.</span> An equilibrium flattens every plane into one number for one year.</div></div>
<div class="handoff">&rarr; Here is that layer, written down.</div>
{FOOT("Fit, gap and what is new",2)}</section>'''

P3=f'''<section class="sheet">
<div class="secnum">03 &middot; THE MODEL</div>
<h2>What each agent <span class="g">decides and remembers</span></h2>
<p>Each year, a household or a firm picks a vehicle, how often to cross, and when. The instruments in force set the cost. Acceptance is estimated first in its plain cross-sectional form (A1), as an integrated choice and latent-variable (ICLV) model on real wave-1 data. This is the hybrid-choice approach used to read acceptance surveys elsewhere [hybridaccept], carried from the bargaining stakeholder groups of Le Pira, Marcucci and Gatta to a whole population of individually estimated agents [lepira].</p>
<div class="eq">(1)&nbsp;&nbsp;U(n,j,t) = &beta;&middot;cost(j, I(t)) + &theta;&prime;&middot;x(n,j) + &epsilon;(n,j,t)<br>(2)&nbsp;&nbsp;A*(n,t) = &rho;&middot;A(n,t&minus;1) + &delta;&middot;dose(n,t) + &eta;&middot;info(n) + &gamma;&prime;&middot;z(n) + u(n,t)<br>(M)&nbsp;&nbsp;I&#8342;(n) = &alpha;&#8342; + &lambda;&#8342;&middot;A*(n) + &nu;&#8342;&nbsp;&nbsp;(attitudinal indicators load on latent acceptance)<br>(3)&nbsp;&nbsp;a pathway is admissible if the share with A* &ge; &lambda; holds every year; its acceptance margin is the largest rise in &lambda; it survives.</div>
<p>Acceptance is a hidden variable. We measure it through survey questions: is the charge fair, is it trusted, is it worth its purpose? Equation (M) ties those answers to it, and the model estimates acceptance jointly with people&rsquo;s choices. Tastes vary across the population, so &beta; is random with a normal spread. This is the full ICLV, not a simple attitude score. The dynamic form (2) adds one memory term, &rho;, found between the two survey waves with the initial-conditions problem handled [wooldridge]. <span class="b">H1 tests &rho; and H2 tests &eta;, both on page 4.</span> &rho; is the stretch, pursued only if both waves land. The core rests on the cross-sectional model.</p>
<p>The estimated numbers then drive a custom agent model in Python and NumPy. Each year, agents replace cars by a binary logit, choose modes by the estimated MNL, and hit congestion on a BPR curve solved by successive averages. That is the engine that carries acceptance and fleet forward, year by year. <span class="b">It already runs, end to end.</span></p>
<div class="twocol">
<div class="plate"><span class="plabel">What memory does</span>{img("memory")}
<div class="cap">Three agents to 2050. The commuter crosses the line &lambda; in 2031 and, because &rho; is high, stays above it. The occasional crosser never leaves. The van driver, with the biggest dose, falls below &lambda; from 2035. <span class="d">Memory, not this year&rsquo;s bill, decides who stays accepting. That is the thing an equilibrium cannot hold.</span> <span class="tier">ILLUSTRATIVE &middot; &rho;, dose not estimates</span></div></div>
<div class="plate"><span class="plabel">One household, three moments</span>{img("household")}
<div class="cap">2026: the household opposes the package, on a fossil car. 2029: it buys electric, the bill drops 30 percent, and acceptance carries forward. 2035: the discount ends, and acceptance drops. <span class="d">The same &rho; that holds acceptance up in 2029 is what lets it fall in 2035. Memory cuts both ways.</span></div></div></div>
<p><span class="b">What a pathway is.</span> Five instruments: revising the package, the zero-emission rate, a passenger distance charge, a heavy-vehicle distance charge, and earmarking the revenue. A3 is a search, not a catalogue. It picks each instrument&rsquo;s switch-on year and level to put the most futures on all three 2050 targets and to minimise the worst-case regret, while keeping acceptance above the line every year, revenue above debt service, and access above a floor. A many-objective robust algorithm does the search; scenario discovery names where the robust set still breaks [prim, mordm]. Robustness as the thing to optimise follows the stability-metrics line of Shaabani, Hvattum, Hoff and Laporte [shaabani]. A reduced set of four instruments enumerates to 4 + 36 + 216 + 648 = 904 ordered sequences, kept as a check; the full search over years and levels runs to about 10&#8308; pathways.</p>
<table class="ttable"><tr><th>Target in 2050</th><th>Metric</th><th>Anchor</th></tr>
<tr><td class="k">Emissions</td><td>Well-to-wheel CO&#8322;e from road traffic in the case area</td><td>Climate Change Act: 90 to 95% by 2050 [klimalov]</td></tr>
<tr><td class="k">Finance</td><td>Toll revenue at or above debt service; failure if below for three years</td><td>Package financing [innst337]</td></tr>
<tr><td class="k">Access (equity)</td><td>Generalised cost of the lowest income quintile no higher than 2026</td><td>The equity the call names; page 4 shows its spatial side</td></tr></table>
<p><span class="b">What would prove it wrong.</span> If &rho; is near zero, agents need no memory and claim 1 collapses to a static result. If &eta; is near zero, information does not move acceptance and H2 fails. If the fast engine cannot match the network model, the ensemble shrinks to what the network model can run. Each is reported whichever way it falls. <span class="b">Tools.</span> Python throughout: Biogeme for estimation, the custom agent model to carry state, EMA Workbench for the futures and the search, OSMnx and NetworkX for the networks, OR-Tools for routing, NGM for freight. The whole chain already runs. As a check I reproduced a standard mixed logit on the public Swissmetro data in Biogeme: final log-likelihood &minus;5214.9 against the published &minus;5214.8 [evdcm]. The code is open and tested.</p>
<div class="handoff">&rarr; Tested where acceptance is live and freight is real.</div>
{FOOT("The model",3)}</section>'''

P4=f'''<section class="sheet">
<div class="secnum">04 &middot; CASE AND DESIGN</div>
<h2>Kristiansund, where <span class="g">acceptance is live</span></h2>
<p><span class="b">Why Kristiansund, and where freight enters.</span> Bypakke Kristiansund began collecting on 1 June 2026, at two rv70 stations, Nordsundbrua and Omsundbrua. About 70 percent of the package is toll-financed, over up to 15 years [bypakke, innst337]. A car pays NOK 34, or 27.20 with a tag, or 19.04 if it is zero-emission with a tag [vegamot]. The council approved the basis 26 to 19, the county 33 to 14. Acceptance here is contested, and live. The town sits on the M&oslash;re og Romsdal corridor, where the Ferjefri E39 programme and NGM both treat coastal short-sea as the competing mode for freight bound to Oslo and the continent [ngm]. Freight is estimated here, not borrowed. A short carrier choice block asks hauliers how they would move, and when, under a distance charge, and the NGM chains carry that answer to the network. The heavy fleet turns over slowly and the sea route needs volume to stay viable, so a pathway that charges road freight too late shuts the modal-shift window and locks the emissions in. <span class="b">Molde, with no package, is the no-toll control town:</span> information without experience, set against Kristiansund&rsquo;s information plus experience.</p>
<div class="plate"><span class="plabel teal">The toll is a map of who can avoid it</span>{img("kmap")}
<div class="cap">Every building is tied to the side of Nordsundbrua it can reach without the bridge, on the real OSM graph. Red is Nordlandet, which only the bridge connects: 48 percent of junction-pairs lose every road link at the split. Teal is the toll-free Atlanterhavstunnelen, a free way out for some. <span class="d">Exposure is geography. The equity target on page 3 is income. The thesis reports one crossed with the other, so the floor is about who pays, not just where.</span> <span class="tier">REAL &middot; OSM graph</span></div></div>
<div class="twocol"><div>
<h3>The survey: three blocks, Bayesian D-efficient</h3>
<p class="small"><b>Acceptance block</b> (households). Information is randomised in three arms: personal cost, a short purpose note, and a control. So both the content and the framing are tested. <b>Passenger choice block.</b> Vehicle at next replacement, crossing frequency and time, at national tariff levels. <b>Carrier choice block</b> (firms and hauliers). Road against coastal short-sea, route and timing under a distance charge. One wave, a small targeted sample, anchored to NGM, reached through freight-industry channels. Kristiansund carries the household and carrier design; Molde the acceptance control. Wave 1 and the carrier block in month 6; wave 2 in month 18, same households. The planning sample is 1,428 in Kristiansund and 714 in Molde, set by the smallest effect worth detecting.</p>
<h3>Three hypotheses</h3>
<p class="small"><b>H1.</b> Acceptance lasts once a charge is permanent (&rho; &gt; 0 in eq. 2), tested as within-person change between waves against dose. <b>H2.</b> Information moves acceptance on its own (&eta; &ne; 0 in eq. 2), tested by the randomised arms and the Molde control, turning the Norwegian link between information and attitude [odeck08] into a causal estimate. <b>H3.</b> A distance charge pushes carrier mode choice toward short-sea above a threshold rate.</p></div>
<div>
<h3>Ethics and data</h3>
<p class="small">The two waves re-link the same households twelve months apart, so identifiers are kept for a year. Lawful basis under GDPR Article 6; consent to re-contact taken at wave 1; the key held apart from the answers, by the supervisor; a written retention-and-deletion schedule; attitudinal data kept to a minimum. The study is notified to Sikt before any fieldwork, with a Data Management Plan filed. Traffic data are used as aggregate station counts only. SSB and RVU microdata are applied for in week 1, under their own agreements.</p>
<h3>If the freight survey comes up short</h3>
<p class="small">The freight arm then stands on NGM&rsquo;s mode-split elasticities, with the key elasticity swept and reported. The freight signpost rests on a national model instead of a local estimate. It is a floor, not a retreat. The freight result holds either way.</p></div></div>
<div class="dark-inset"><div class="dl">Molde &middot; the same method, on a second real network</div>{img("molde_pinch",style="max-height:340px;object-fit:cover;object-position:center")}
<div class="dc">Route a van between every pair of junctions on Molde&rsquo;s real road graph. 18 percent of all fastest routes funnel through one street, &Oslash;vre veg. Close it and 32 percent of trips slow, 0.9 percent strand. Kristiansund&rsquo;s bridge is the same fragility, 48 percent of junction-pairs cut. Measured on two real towns, not assumed. <span class="tier" style="color:#8fb0c4;border-color:#2a3647">REAL &middot; Molde OSM &middot; betweenness</span></div></div>
<div class="handoff">&rarr; And here is how it finishes in three years.</div>
{FOOT("Case and design",4)}</section>'''

P5=f'''<section class="sheet">
<div class="secnum">05 &middot; PLAN, ROBUSTNESS AND RECEIPTS</div>
<h2>How it <span class="g">finishes in three years</span></h2>
<div class="ladder"><div class="lh">A thesis that survives a failed survey</div>
<div class="lrow"><span class="ln">Level 1</span><span>No new data. A1 on national ranges, A3 on NGM elasticities, freight included. A complete thesis on its own.</span></div>
<div class="lrow"><span class="ln">Level 2</span><span>Wave 1 and the carrier block. Adds H2, a cross-sectional A2, and estimated freight.</span></div>
<div class="lrow"><span class="ln">Level 3</span><span>Both waves. Adds H1 and the memory term &rho;, the stretch.</span></div>
<p class="small" style="margin:7px 0 0">Each level is a finished dissertation. The survey only raises the ceiling. The guaranteed floor is my own collected data, under my control. That is how this finishes in 36 months, even if the microdata or a survey wave never arrives.</p></div>
<p><span class="b">The search, priced.</span> A3 explores about 10&#8308; candidate pathways, each scored against a Latin-hypercube sample of futures, and the robust set is re-checked on the full 1,000. Each run advances a zonal state to 2050 in about 25 ms, so the budget is 40 to 150 CPU-hours, parallel, inside a desktop over a weekend. Fidelity is measured on two real networks, Molde and Kristiansund: the fast engine matches static-network car times per zone pair to about 15 percent (r 0.73 to 0.84). A dynamic MATSim cross-check (Molde, 4,000 agents) matches to about 19 percent at free flow and to 6 percent on the static assignment, and the free-flow engine breaks under a tenfold capacity squeeze. That is why robust pathways are re-checked on the network model [evfid].</p>
<div class="plate"><span class="plabel">The robust front, and the order each pathway switches on</span>{img("front")}
<div class="cap">Each dot is one of 904 pathways, scored on acceptance margin and share of futures on target. The front is the best trade-off; E is chosen for the widest shift in &lambda; it survives. The rail below is the finding the scatter cannot show. <span class="d">The same instruments in a different order give a different fate.</span> A opens with the zero-emission rate and fails. E earmarks first, then charges distance, and holds. The order is the result. <span class="tier">PROTOTYPE &middot; parameters assumed until A1 to A3 &middot; 10 seeds &middot; hypervolume-converged</span></div></div>
<div class="twocol">
<div class="plate"><span class="plabel">What replaces the lost revenue</span>{img("erosion")}
<div class="cap">Revenue over debt across 1,000 futures. 22 percent fail to cover the debt before 2041, 30 percent by 2050. <span class="d">This is the page-1 erosion grown up. The minus-30-percent-a-crossing becomes a debt-cover signpost, and the year the median future crosses the debt line is the finance signpost the ring promised.</span> <span class="tier">PROTOTYPE</span></div></div>
<div><div class="vpanel"><div class="tcat" style="color:var(--gold)">Claim 2 &middot; uncertainty by source</div>
<p class="small" style="margin:4px 0 6px">Where the 2050 spread comes from, by year. Planners see which uncertainty more data can cut (behaviour) and which only adaptation can (outside futures).</p>
<div style="font-family:Montserrat;font-size:9px;letter-spacing:.5px;color:var(--mut);display:flex;justify-content:space-between"><span>2026</span><span>2038</span><span>2050</span></div>
<div class="vbar"><span style="background:var(--terra);width:42%">BEHAVIOUR 42%</span><span style="background:var(--gold);width:37%">FUTURES 37%</span><span style="background:var(--sage);width:21%">PATH 21%</span></div>
<p class="small" style="margin:4px 0 0;color:var(--mut);font-style:italic">Sobol variance shares, prototype. Behaviour dominates early, so more survey data helps. Outside futures dominate late, so only adaptation does.</p>
<div class="tier" style="margin-top:7px;display:inline-block">PROTOTYPE &middot; illustrative</div></div>
<table class="ttable" style="margin-top:8px"><tr><th>Article</th><th>Submit</th><th>Data</th></tr>
<tr><td>A1 Choice estimated</td><td>M12</td><td>Wave 1 + carrier block</td></tr>
<tr><td>A2 Acceptance that lasts</td><td>M24</td><td>Both waves</td></tr>
<tr><td>A3 Robust pathways</td><td>M30</td><td>Ensemble; dated events</td></tr></table></div></div>
<h3>The computational stack, one tool per article</h3>
<div class="tools">
<div class="tcol"><div class="tcat">Estimate</div><div class="ttool">Biogeme</div><div class="ttool s">mixed logit, ICLV</div><div class="trole">Acceptance and carrier mode choice, from real survey data.</div><div class="tart">A1, A2</div></div>
<div class="tcol"><div class="tcat">Carry</div><div class="ttool">Agent model</div><div class="ttool s">Python, NumPy</div><div class="trole">Fleet logit, estimated MNL, BPR congestion. Acceptance and fleet carried year to year.</div><div class="tart">A2, A3</div></div>
<div class="tcol"><div class="tcat">Explore</div><div class="ttool">EMA Workbench</div><div class="ttool s">&epsilon;-NSGA-II, PRIM</div><div class="trole">1,000 futures, robust search, scenario discovery.</div><div class="tart">A3</div></div>
<div class="tcol"><div class="tcat">Network</div><div class="ttool">OSMnx, NetworkX</div><div class="ttool s">OR-Tools, MATSim</div><div class="trole">Real road graphs, routing checks, dynamic cross-check.</div><div class="tart">A1, A3</div></div>
<div class="tcol"><div class="tcat">Freight</div><div class="ttool">NGM</div><div class="ttool s">national freight model</div><div class="trole">Commodity chains, mode split, load factors, empty running.</div><div class="tart">A3</div></div>
<div class="tcol"><div class="tcat">Compose</div><div class="ttool">Rhino, Grasshopper</div><div class="ttool s">Ladybug, Blender</div><div class="trole">Every figure computed from the data, in one parametric pipeline.</div><div class="tart">all plates</div></div></div>
<div class="twocol"><div>
<h3>Calendar: 36 months, full research</h3>
<p class="small">Week 1: the SSB and RVU applications and the Sikt notice go in, off the critical path. Months 1 to 6: coursework, including philosophy of science and discrete-choice courses, and a pilot with Norwegian-speaking co-authors. Month 6: wave 1 and the carrier block. Month 12: A1. Month 18: wave 2. Month 20: midway evaluation. Month 24: A2. Month 30: A3, with six months left for the summary chapter and the defense. Articles are pipelined, not serial: A1 is under review while A2 runs.</p>
<h3>Risk and response</h3>
<table class="ttable"><tr><th>Risk</th><th>Response</th></tr>
<tr><td class="k">Low response or attrition</td><td>Panel top-up; sample sized for it; Level 2 holds</td></tr>
<tr><td class="k">No microdata by M6</td><td>Published ranges and NGM; the spine is my own survey</td></tr>
<tr><td class="k">Carrier survey short</td><td>Stand on NGM elasticities, sweep the key one</td></tr>
<tr><td class="k">Language</td><td>Instrument in English, translated and piloted with Norwegian co-authors</td></tr></table></div>
<div>
<h3>Supervision and fit</h3>
<p class="small">The supervision this work needs is resident in the department. Robustness and stability metrics: the group behind [shaabani], Hvattum and Hoff. Discrete choice: the tradition of [lepira], Marcucci and Gatta, the one skill I set out to deepen. Freight and toll economics: the ground of [odeck08], Odeck and Br&aring;then, and the Logistics department itself. The three works this proposal leans on hardest were each written inside Molde&rsquo;s own groups. All the modelling and evidence so far is my own.</p>
<h3>Why here, and the decision it yields</h3>
<p class="small">The position sits in the Department of Logistics and asks for behaviour under the zero-emission transition, with its effect on finance and equity. That is this proposal&rsquo;s spine. The thesis ends on a concrete recommendation: a revised zero-emission discount and tariff for Bypakke Kristiansund, not just a method. <b>Receipts.</b> Every number traces to a tagged commit, with 89 automated tests, and every figure is drawn by the same code. The code is open; anonymised data is deposited FAIR once Sikt allows; AI-tool use is disclosed. <b>Dissemination.</b> Three journal articles, a Norwegian-language piece in <i>Samferdsel</i>, and the annual NORS conference, where I have presented before.</p></div></div>
<div class="handoff">&rarr; The finance signpost that warns a path is failing is the same erosion page 1 showed already under way. The ring closes.</div>
{FOOT("Plan, robustness and receipts",5)}</section>'''

# PAGE 6 reuse from v57 build (references + ledger + thesismap), but strip em dashes
exec(open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/v57/_p6_58.py").read())  # defines P6

html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>From end states to pathways</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Spectral:ital,wght@0,400;0,500;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>{P1}{P2}{P3}{P4}{P5}{P6}</body></html>'''
open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/v57/proposal58.html","w").write(html)
print("proposal58.html", len(html)//1024,"KB")
