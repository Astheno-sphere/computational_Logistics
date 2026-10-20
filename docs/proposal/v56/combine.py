import json, base64
E=json.load(open("figs_extra.json")); FIG3,FIG5B=E["FIG3"],E["FIG5B"]
RF=open("rf_inner.txt").read()
FIGFREIGHT=json.load(open("freight.json"))["FIGFREIGHT"]
MAP="data:image/jpeg;base64,"+base64.b64encode(open("/tmp/claude-0/-home-claude/0a646ebe-b26f-5896-8bfd-9fc85a0e6d3f/scratchpad/kristiansund_map.jpg","rb").read()).decode()
CSS=open("_CSS.txt").read()
p12=open("content_p12.txt").read().split("\n@@@\n"); page1,page2=p12[0],p12[1]
exec(open("pages356.py").read())  # defines page3,page4,page5,page6
head='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>From end states to pathways</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&family=Spectral:ital,wght@0,400;0,500;0,600;1,400;1,500&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet"><style>'+CSS+'</style></head><body>'
doc=head+page1+page2+page3+page4+page5+page6+"</body></html>"
open("proposal.html","w").write(doc)
print("proposal.html",len(doc)//1024,"KB")
