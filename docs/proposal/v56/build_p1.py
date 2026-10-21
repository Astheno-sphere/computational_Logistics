exec(open("fig1_parts.py").read())
css=open("page1.css").read()
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>From end states to pathways · 1</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Spectral:ital,wght@0,400;0,500;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}</style></head><body>
<section class="sheet">
  <div class="kick">Research proposal · TRANSPLAN · Molde University College</div>
  <div class="doctitle">From end states to <span class="g">pathways</span></div>
  <div class="docsub">Estimated acceptance, agents with memory, and robust road-pricing paths to a low-carbon Norway in 2050</div>
  <div class="byline">Arshad Akhtar Abbasia · PhD in Transport Modelling for Sustainability Transitions · PhD programme in Logistics</div>
  <div class="hr"></div>

  <div class="secnum">01 · THE PROBLEM</div>
  <h2>What an equilibrium <span class="g">cannot carry</span></h2>

  <p>Norway appraises transport with a national model system that computes an equilibrium for a chosen year. Asked what 2050 looks like under a set of assumptions, it answers carefully. Asked how the country gets there, and which routes fail on the way, it is silent by construction. TØI&rsquo;s own review says as much: the current models are <span class="b">static and macroscopic</span>, and less suited to dynamic questions [toi1819]. The path to 2050 is governed by what an equilibrium does not carry: a vehicle fleet that turns over slowly, public acceptance that persists or erodes, and debt repaid on a schedule.</p>

  <p>Road pricing shows the problem in its sharpest form. It is named among the levers for the next National Transport Plan, where TRANSPLAN&rsquo;s first deliverable argues the plan must be <span class="b">realistic and goal-directed</span> rather than a wish list [toi2172]; yet the national reform has stalled. Tolls raised NOK 16.8 billion in 2025, about 62% in city packages, against toll-company debt near NOK 78 billion [svv25]. Every revision meets a public that has voted against tolls before: a single-issue anti-toll party won 16.7% in Bergen in 2019 [snl19]. Whether a 2050 plan is feasible depends on the order in which instruments arrive and whether people accept each step. <span class="b">That is a question about paths.</span></p>

  <div class="rqbox">
    <div class="mq">Main question. Which sequences of road-pricing instruments reach a desirable 2050 on emissions, finance and accessibility while staying acceptable to the people and firms who pay, across deep uncertainty; and which signals tell planners when to switch?</div>
    <div class="rq"><b>RQ1 · method</b>How can choice models estimated on real data drive agents that carry state year to year, so strategic end states become pathways?</div>
    <div class="rq"><b>RQ2 · behaviour</b>Does acceptance persist once a charge is permanent, and does information move it independently of experience?</div>
    <div class="rq"><b>RQ3 · planning</b>Which pathways, for passengers and for freight, are robust; what acceptance margin does each survive; and which signposts give lead time before one fails?</div>
  </div>

  <p><span class="b">What already exists.</span> I have a working prototype and a first measured result. At the Kristiansund tariff a zero-emission car with a tag pays NOK 19.04 against NOK 27.20, so each electric crossing earns NOK 8.16, or 30%, less [vegamot]. On the road network, the toll-free Atlantic Ocean Tunnel lets some crossings avoid both stations; Article 1 counts that share ([N1]), so exposure is measured on the network, not assumed uniform. The question is no longer whether the toll base erodes; it is which path through that erosion people will accept.</p>

  <div class="figrow">
    <div class="plate">
      <span class="platelabel">One place, three moments</span>
      {FIG1A}
      {LEG1A}
      {TIMELINE}
    </div>
    <div class="plate">
      <span class="platelabel teal">What a crossing earns</span>
      {FIG1B}
      <div class="figcap">A model gives one 2050. The toll base is already moving under it.</div>
    </div>
  </div>
  <div class="figcap" style="margin-top:12px">The same town, the same stations; the fleet electrifies, the revenue per crossing falls, the debt does not. Exposure is read from the OpenStreetMap graph; the electric share is from the prototype. Acceptance is not drawn here &mdash; it is the quantity the thesis sets out to estimate (page 3).</div>

  <div class="handoff">&rarr; So Norway needs the dynamic layer TØI calls for. What should it be, and who has built the pieces?</div>

  <div class="foot"><span>Arshad Akhtar Abbasia</span><span>From end states to pathways</span><span class="r">github.com/Astheno-sphere/computational_logistics &nbsp;·&nbsp; 1 / 6</span></div>
</section></body></html>'''
open("page1.html","w").write(html)
print("page1.html", len(html)//1024,"KB")
