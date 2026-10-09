#!/usr/bin/env python3
"""Number references in order of first citation.

Sources cite with <sup>key</sup> or <sup>key,key</sup>, where key is a short id from REFS below. The
references block is <ol data-refs></ol>; renumber(html) fills it and replaces keys with numbers.
"""
import re

REFS = {
    "ofv": "OFV (2026) New passenger car registrations, 2025.",
    "wps": "Wangsness, Proost &amp; Steinsland (2026) The curious case of road pricing reform in Norway. <i>Transportation Research Interdisciplinary Perspectives</i> 38, 102064.",
    "ntp": "Ministry of Transport (2024) Meld. St. 14 (2023–2024) <i>National Transport Plan 2025–2036</i>.",
    "oppdrag": "Ministry of Transport and Ministry of Trade, Industry and Fisheries (2024) NTP-oppdrag nr. 1-2024.",
    "transplan": "TØI. TRANSPLAN, Norwegian Centre for Sustainable Transport Planning (2025–2033).",
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
    head, sep, tail = html.partition("<ol data-refs>")
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
