# -*- coding: utf-8 -*-
CSS = """
:root{--bg:#15181c;--ink:#E9E3D7;--mut:#98a0a8;--gold:#D4A530;--teal:#7CBAC4;--line:#2b3138}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#0d0f12}
.page{width:794px;min-height:1123px;margin:0 auto;background:var(--bg);color:var(--ink);
  font-family:Spectral,Georgia,serif;padding:58px 68px 40px;display:flex;flex-direction:column}
.name{font-family:Montserrat;font-weight:800;font-size:29px;letter-spacing:-.3px;color:var(--ink);line-height:1}
.name .g{color:var(--gold)}
.contact{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--mut);letter-spacing:.2px;margin-top:9px;line-height:1.7}
.contact .l{color:var(--teal)}
.rule{height:2px;background:var(--gold);width:54px;margin:16px 0 20px}
.recip{font-family:Montserrat;font-size:11px;line-height:1.6;color:var(--mut);margin-bottom:24px}
.recip .d{color:var(--ink);font-weight:600}
.recip .t{color:var(--ink);font-weight:700;letter-spacing:.2px}
.sal{font-size:14.5px;margin:4px 0 14px}
p{font-size:14px;line-height:1.6;margin:0 0 12px;max-width:none}
.n{color:var(--gold);font-weight:500}
.em{font-style:italic;color:var(--ink)}
.b{font-weight:600}
.sign{margin-top:8px;font-size:14px}
.signame{font-family:Montserrat;font-weight:700;font-size:14px;color:var(--ink);margin-top:3px}
.foot{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:22px;
  border-top:1px solid var(--line);font-family:'JetBrains Mono',monospace;font-size:9.5px;color:var(--mut);letter-spacing:.3px}
.foot .r{color:var(--gold)}
"""

BODY = """
<div class="name">Arshad Akhtar <span class="g">Abbasia</span></div>
<div class="contact">Sollivegen 97F, 6414 Molde &middot; +47 96 73 02 90 &middot; arshad.a.abbasia@himolde.no<br>
<span class="l">github.com/Astheno-sphere/computational_logistics</span></div>
<div class="rule"></div>
<div class="recip"><span class="d">21 October 2026</span><br>
<span class="t">Appointment committee &middot; PhD Research Fellow, TRANSPLAN</span><br>
Jobbnorge 308701 &middot; Department of Logistics, Molde University College</div>
<div class="sal">Dear members of the committee,</div>
<p>I am applying for the TRANSPLAN fellowship with the proposal <span class="em">From end states to pathways</span>, which I have already started building. The call says the proposal is the most important criterion, so this letter is short and points to the evidence there.</p>
<p>I am a mechanical engineer finishing an MSc in Sustainable Energy Logistics at HiMolde (2024 to 2026). Before the master I spent four years in cross-border procurement and freight logistics across the DACH region, India and the UAE. The engineering gave me systems and optimisation; the procurement years gave me the freight side the proposal leans on, including how carriers actually weigh road against sea.</p>
<p>The method is already under construction, not only described. The pipeline runs end to end in a public repository with <span class="n">89 tests</span>, and two real road networks, Kristiansund and Molde, are already benchmarked. Before trusting that pipeline on data I will estimate myself, I checked it against a known answer: a published mixed logit on Swissmetro, reproduced in Biogeme to the fourth decimal, <span class="n">&minus;5214.9 against &minus;5214.8</span>. That is the machinery the acceptance estimation runs on. The estimation itself is the thesis.</p>
<p>The layer sits beside the national models, not over them. It is the dynamic, acceptance-based layer that T&Oslash;I 1819/2021 asked for and that <span class="em">Veivalg</span> (T&Oslash;I 2172/2026) argues TRANSPLAN needs for pricing and capacity. Freight is estimated, not bolted on: Kristiansund&rsquo;s live Bypakke toll, Molde as the no-toll control, and the Ferjefri E39 corridor where the freight signpost should fire first. If the carrier sample is thin it stands on national elasticities, so the result holds either way. Acceptance enters as an admissibility condition, <span class="n">&lambda;</span>, inside a robust min-max-regret search over pricing pathways to 2050, not a survey reported after the model has run.</p>
<p>This is not my first novel computational build. My MSc thesis produced a verifiable crypto-erasure method for cross-border audit trails, which I presented at NORS 2025. The subject differs; the discipline, a tested artefact for a real policy problem, is the same.</p>
<p>The work is scoped as three articles at <span class="n">months 12, 24 and 30</span>, inside the three years. The supervision it needs, discrete choice, robustness and freight, is resident in this department, which is part of why I am applying here. The survey instrument is drafted in English and piloted with Norwegian-speaking co-authors.</p>
<p>Enclosed are the five-page proposal, my CV, diplomas and transcripts, my MSc thesis abstract, and three referees. I would welcome an interview to discuss the estimation and the three-year plan.</p>
<div class="sign">Yours sincerely,</div>
<div class="signame">Arshad Akhtar Abbasia, Molde</div>
<div class="foot"><span>From end states to pathways &middot; TRANSPLAN proposal enclosed</span><span class="r">github.com/Astheno-sphere/computational_logistics</span></div>
"""

html=f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&family=Spectral:ital,wght@0,400;0,500;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="page">{BODY}</div></body></html>"""
open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/letter/letter.html","w",encoding="utf-8").write(html)
print("letter.html written", len(html)//1024,"KB")
