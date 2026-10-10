#!/usr/bin/env python3
"""Number references in order of first citation.

Sources cite with <sup>key</sup> or <sup>key,key</sup>, where key is a short id from REFS below. The
references block is <ol data-refs></ol>; renumber(html) fills it and replaces keys with numbers.
"""
import re

REFS = {
    "wooldridge": "Wooldridge (2005) Simple solutions to the initial conditions problem in dynamic, nonlinear panel data models with unobserved heterogeneity. <i>Journal of Applied Econometrics</i> 20(1), 39–54.",
    "odeck08": "Odeck &amp; Bråthen (2008) Travel demand elasticities and users attitudes: a case study of Norwegian toll projects. <i>Transportation Research Part A</i> 42(1), 77–94.",
    "tramodsim": "Flügel, Flötteröd et al. (2023) <i>TraModSim: an open-source traffic assignment tool for TraMod_By based on MATSim</i>. TØI report 1993/2023.",
    "toi2035": "Flügel, Weber &amp; Hamre (2024) TØI report 2035/2024 on modelling new mobility and flexible tolls beyond the regional transport model.",
    "toi2172": "Halse, Wangsness, Babri, Tveter, Bråthen &amp; Olsen (2026) <i>Veivalg for en realistisk og målrettet transportplan</i>. TØI report 2172/2026.",
    "power": "Tveter &amp; Holmgren (2024) Statistical power and productivity effects of transport investments: a critical review. <i>Research in Transportation Economics</i> 105.",
    "ofv": "OFV (2026) New passenger car registrations, 2025.",
    "wps": "Wangsness, Proost &amp; Steinsland (2026) The curious case of road pricing reform in Norway. <i>Transportation Research Interdisciplinary Perspectives</i> 38, 102064.",
    "ntp": "Ministry of Transport (2024) Meld. St. 14 (2023–2024) <i>National Transport Plan 2025–2036</i>.",
    "oppdrag": "Ministry of Transport and Ministry of Trade, Industry and Fisheries (2024) NTP-oppdrag nr. 1-2024.",
    "transplan": "TØI (2025) TRANSPLAN: A transport system within planetary boundaries. Centre for transport research, 2025–2033. toi.no/transplan.",
    "toi2051": "Kristensen et al. (2024) <i>Transport demand in foresight and backcasting</i>. TØI report 2051/2024.",
    "big": "Fridstrøm, Østli &amp; Johansen (2016) A stock-flow cohort model of the national car fleet. <i>European Transport Research Review</i> 8.",
    "toi2179": "Ciccone, Halse, Andreassen, Garnache &amp; Wangsness (2026) <i>Acceptance of distance-based road pricing: national choice experiment and field trial in the Oslo region</i>. TØI report 2179/2026.",
    "accept": "Börjesson, Eliasson, Hugosson &amp; Brundell-Freij (2012) <i>Transport Policy</i> 20; Hess &amp; Börjesson (2019) <i>Transportation Letters</i> 11(2).",
    "lepira": "Le Pira, Marcucci, Gatta, Inturri, Ignaccolo &amp; Pluchino (2017) <i>Research in Transportation Economics</i> 64; Gatta et al. (2020) <i>Transportation Research Procedia</i> 46.",
    "petrik": "Petrik, Adnan, Basak &amp; Ben-Akiva (2020) <i>Future Generation Computer Systems</i> 110; Petrik, Moura &amp; de Abreu e Silva (2016) <i>Transportation Planning and Technology</i> 39(2).",
    "tveter25": "Tveter, Welde &amp; Odeck (2025) Accounting for uncertainties in cost-benefit analyses of road projects. <i>Transport Policy</i> 170.",
    "raso": "Raso, Kwakkel &amp; Timmermans (2019) Assessing the capacity of adaptive policy pathways to adapt on time. <i>Sustainability</i> 11(6), 1716.",
    "haasnoot": "Haasnoot, van ’t Klooster &amp; van Alphen (2018) Designing a monitoring system to detect signals to adapt. <i>Global Environmental Change</i> 52.",
    "toi2119": "Wangsness et al. (2025) <i>Methods, processes and example calculations for strategies towards a carbon-neutral transport sector in 2050</i>. TØI report 2119/2025.",
    "domarchi": "Domarchi &amp; Cherchi (2023) Electric vehicle forecasts: a review of models and methods. <i>Transport Reviews</i> 43(6).",
    "svv": "Statens vegvesen (2025) Klimagassutslipp fra transport. vegvesen.no.",
    "svv25": "Statens vegvesen (2026) Bompengerapport 2025: flere passeringer og økte inntekter. vegvesen.no.",
    "dok15": "Samferdselsdepartementet (2026) Answer to written question Dok. 15:1376 (2025–2026) on toll revenue by project type. stortinget.no.",
    "svvev": "Statens vegvesen (2026) Fire av ti bompasseringer skjer nå med elbil. vegvesen.no, September 2026.",
    "vegamot": "Vegamot (2026) Takster, Bypakke Kristiansund. vegamot.no.",
    "snl19": "Store norske leksikon. Kommunestyre- og fylkestingsvalget 2019. snl.no.",
    "borjesson16": "Börjesson, Eliasson &amp; Hamilton (2016) Why experience changes attitudes to congestion pricing: the case of Gothenburg. <i>Transportation Research Part A</i> 85, 1–16.",
    "toi2141": "TØI (2026) Report 2141/2026 on the effects of the 2019 toll restructuring in Oslo and Akershus.",
    "edmondson": "Edmondson, Flachsland, aus dem Moore, Koch et al. (2025) Anticipatory climate policy mix pathways. <i>Climate Policy</i> 25(3), 438–467.",
    "dapp": "Haasnoot, Kwakkel, Walker &amp; ter Maat (2013) Dynamic adaptive policy pathways. <i>Global Environmental Change</i> 23(2), 485–498.",
    "bypakke": "Statens vegvesen (2024–2025) Bypakke Kristiansund: faglig grunnlag vedtatt i bystyret; bypakken vedtatt; vedtok Bypakke Kristiansund. vegvesen.no.",
    "innst337": "Stortinget (2025) Innst. 337 S (2024–2025) on Bypakke Kristiansund.",
    "osm": "OpenStreetMap contributors (2026) Road network of Kristiansund and Molde, ODbL.",
    "welde19": "Welde, Tveter &amp; Odeck (2019) The traffic effects of fixed links: short and long-run forecast accuracy. <i>Transportation Research Procedia</i> 42.",
    "deuten": "Deuten, Gómez Vilchez &amp; Thiel (2020) Analysis and testing of electric car incentive scenarios in the Netherlands and Norway. <i>Technological Forecasting and Social Change</i> 151.",
    "pom": "Grimm et al. (2005) Pattern-oriented modeling of agent-based complex systems. <i>Science</i> 310.",
    "odd": "Grimm et al. (2020) The ODD protocol: a second update. <i>Journal of Artificial Societies and Social Simulation</i> 23(2).",
    "mordm": "Kasprzyk, Nataraj, Reed &amp; Lempert (2013) <i>Environmental Modelling &amp; Software</i> 42; Kwakkel (2017) <i>Environmental Modelling &amp; Software</i> 96.",
    "prim": "Bryant &amp; Lempert (2010) Thinking inside the box. <i>Technological Forecasting &amp; Social Change</i> 77(1).",
    "hoff": "Shaabani, Hvattum, Laporte &amp; Hoff (2024) Stability metrics for a maritime inventory routing problem under sailing time uncertainty. <i>EURO Journal on Transportation and Logistics</i> 13.",
    "story": "Marcucci, Lozzi &amp; Gatta (2026) Crafting consensus in city logistics: the power of storytelling. <i>Transportation Research Procedia</i> 98.",
    "lyons": "Lyons &amp; Davidson (2016) Guidance for transport planning and policymaking in the face of an uncertain future. <i>Transportation Research Part A</i> 88.",
    "toi2081": "Pinchasik, Grimsrud &amp; Tveit (2025) <i>Developing Norway’s National Transport Plan into a more strategic and improved policy tool</i>. TØI report 2081/2025.",
}


def renumber(html):
    m = re.search(r"<ol data-refs[^>]*>", html)
    if not m:
        raise ValueError("no <ol data-refs> block")
    head, sep, tail = html[:m.start()], m.group(0), html[m.end():]
    order = []
    for m in re.finditer(r"<sup>([a-z0-9,]+)</sup>", head):
        for k in m.group(1).split(","):
            if k not in REFS:
                raise KeyError(f"unknown reference key {k!r}")
            if k not in order:
                order.append(k)
    num = {k: i + 1 for i, k in enumerate(order)}
    head = re.sub(r"<sup>([a-z0-9,]+)</sup>", lambda m: "<sup>" + ",".join(str(num[k]) for k in m.group(1).split(",")) + "</sup>", head)
    items = "".join(f"<li>{REFS[k]}</li>" for k in order)
    return head + sep + items + tail
