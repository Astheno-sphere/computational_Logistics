exec(open("fig2_parts.py").read())
css=open("page1.css").read()
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fit, gap · 2</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Spectral:ital,wght@0,400;0,500;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}</style></head><body>
<section class="sheet">
  <div class="secnum">02 · FIT, GAP AND WHAT IS NEW</div>
  <h2>A dynamic layer <span class="g">beside</span> the national models</h2>

  <p>The national system has three parts a candidate must name: <span class="b">NTM6</span>, the national passenger model for trips over 70 km; <span class="b">RTM</span>, the regional passenger model; and the national freight model, <span class="b">Nasjonal godsmodell (NGM)</span>, with its commodity-flow matrices and transport-chain costs [toi1819, ngm]. These anchor the National Transport Plan and are trusted for point appraisal. TØI&rsquo;s forward-looking review recommends not replacing them but building dynamic models alongside them [toi1819]; the institute has begun, with a MATSim-based agent assignment for Greater Oslo, tramodsim [tramodsim]. This PhD joins that line. It supplies the exploratory, stress-testing layer that sequences instruments across thousands of futures and reports where each sequence fails, so the national models keep producing the appraisal the agencies rely on while this layer supplies the robustness and failure conditions they are not built to give.</p>

  <div class="askgrid">
    <div class="ah">The position asks for</div><div class="ah">This proposal answers with</div>
    <div class="ac l">Desirable futures under deep uncertainty</div><div class="ac">10³ futures, satisficing targets, uncertainty decomposed by source</div>
    <div class="ac l">DCM integrated with ABM</div><div class="ac">Choice models estimated on real survey data drive agents whose acceptance and fleet carry over year to year</div>
    <div class="ac l">Behaviour under low-carbon scenarios to 2050</div><div class="ac">Emissions an explicit objective; passenger acceptance and carrier mode choice both estimated; freight turns over by class, with load factors from NGM</div>
    <div class="ac l">Backcasting and pathways, not one forecast</div><div class="ac">2050 targets defined on page 3; instrument orders searched backward from them</div>
  </div>

  <p><span class="b">The gap.</span> Strategic models give end states and NGM gives freight chains; neither carries acceptance. Norwegian agent work assigns traffic with MATSim but takes acceptance as given [tramodsim]. Le Pira, Marcucci and Gatta integrated discrete choice and agent-based models for urban freight policy [lepira]; their agents are stakeholder groups negotiating in rounds, not a population living through calendar time. Adaptive pathway methods sequence actions against tipping points [haasnoot] but treat acceptance as an external scenario. The deep-uncertainty frontier runs ensembles over transport agent models, most recently on a fictional city with acceptance left out [fuhrer]. <span class="b">Nobody has estimated acceptance on real data, carried it in agents over calendar time, and let it decide which passenger and freight pathways survive.</span></p>

  <div class="heart">The question beneath the whole proposal comes before any pathway: is public acceptance a measurable quantity that can be estimated on real data and carried forward in time, or not? The thesis answers that first; the ensemble and the robust front are what the answer is then used for.</div>

  <div class="claims">
    <div class="claim"><div class="cn">1</div><div class="ct">Acceptance as an admissibility condition</div><p>A pathway counts only if estimated acceptance stays above a threshold at every step; the largest shift it survives is its acceptance margin, a result not an assumption.</p></div>
    <div class="claim"><div class="cn">2</div><div class="ct">Uncertainty decomposed by source</div><p>The spread in 2050 outcomes is split, year by year, into behavioural parameters, external futures and the choice of path, so planners see which more data can reduce.</p></div>
    <div class="claim"><div class="cn">3</div><div class="ct">Signposts validated twice, ordered across modes</div><p>Early-warning signals are scored on held-out futures for lead time and false alarms, then against dated events; passenger and freight signposts are compared.</p></div>
  </div>

  <div class="plate" style="margin-top:4px">
    <span class="platelabel">One network, the layers it must carry</span>
    {FIG2}
    <div class="figcap">Six layers over one Kristiansund street graph. The network is real; fleet, emissions and revenue come from the prototype; <span style="color:#D4835C">choice and acceptance are the quantities this PhD sets out to estimate</span> — drawn dashed because they are not computed yet. An equilibrium collapses all of this into one number for one year.</div>
  </div>

  <div class="handoff">&rarr; Here is that layer, written down.</div>
  <div class="foot"><span>Arshad Akhtar Abbasia</span><span>Fit, gap and what is new</span><span class="r">github.com/Astheno-sphere/computational_logistics &nbsp;·&nbsp; 2 / 6</span></div>
</section></body></html>'''
open("page2.html","w").write(html)
print("page2.html", len(html)//1024,"KB")
