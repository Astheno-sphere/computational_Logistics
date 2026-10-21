# -*- coding: utf-8 -*-
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

GOLD=RGBColor(0xD4,0xA5,0x30); CREAM=RGBColor(0xE9,0xE3,0xD7); TEAL=RGBColor(0x5F,0x9C,0xAD)
DARK=RGBColor(0x1A,0x1C,0x20); MUT=RGBColor(0x5A,0x60,0x68); CHAR="15181C"
BODYF="Georgia"; HEADF="Montserrat"; MONOF="Consolas"

doc=Document()
sec=doc.sections[0]
sec.page_height=Cm(29.7); sec.page_width=Cm(21.0)
sec.top_margin=Cm(1.2); sec.bottom_margin=Cm(1.2); sec.left_margin=Cm(1.9); sec.right_margin=Cm(1.9)

def setfont(run,name):
    run.font.name=name
    r=run._element.rPr.rFonts; r.set(qn('w:ascii'),name); r.set(qn('w:hAnsi'),name); r.set(qn('w:cs'),name)

def shade_cell(cell,hexfill):
    tcPr=cell._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd')
    shd.set(qn('w:val'),'clear'); shd.set(qn('w:color'),'auto'); shd.set(qn('w:fill'),hexfill)
    tcPr.append(shd)

def no_borders(table):
    tbl=table._tbl; tblPr=tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for edge in ('top','left','bottom','right','insideH','insideV'):
        e=OxmlElement('w:'+edge); e.set(qn('w:val'),'none'); e.set(qn('w:sz'),'0'); borders.append(e)
    tblPr.append(borders)

# ---- dark header block (table cell, shaded) ----
t=doc.add_table(rows=1,cols=1); t.autofit=False; no_borders(t)
cell=t.rows[0].cells[0]; shade_cell(cell,CHAR)
cell.width=Cm(17.0)
# cell margins
tcPr=cell._tc.get_or_add_tcPr(); mar=OxmlElement('w:tcMar')
for m,v in (('top',220),('bottom',220),('start',240),('end',240)):
    el=OxmlElement('w:'+m); el.set(qn('w:w'),str(v)); el.set(qn('w:type'),'dxa'); mar.append(el)
tcPr.append(mar)
p=cell.paragraphs[0]; p.paragraph_format.space_after=Pt(2)
r=p.add_run("Arshad Akhtar "); setfont(r,HEADF); r.bold=True; r.font.size=Pt(20); r.font.color.rgb=CREAM
r=p.add_run("Abbasia"); setfont(r,HEADF); r.bold=True; r.font.size=Pt(20); r.font.color.rgb=GOLD
p2=cell.add_paragraph(); p2.paragraph_format.space_before=Pt(4); p2.paragraph_format.space_after=Pt(0)
r=p2.add_run("Sollivegen 97F, 6414 Molde  ·  +47 96 73 02 90  ·  arshad.a.abbasia@himolde.no"); setfont(r,MONOF); r.font.size=Pt(8.5); r.font.color.rgb=RGBColor(0x98,0xA0,0xA8)
p3=cell.add_paragraph(); p3.paragraph_format.space_before=Pt(1)
r=p3.add_run("github.com/Astheno-sphere/computational_logistics"); setfont(r,MONOF); r.font.size=Pt(8.5); r.font.color.rgb=TEAL

# gold rule under header
rule=doc.add_paragraph(); rule.paragraph_format.space_before=Pt(6); rule.paragraph_format.space_after=Pt(10)
pPr=rule._p.get_or_add_pPr(); pbdr=OxmlElement('w:pBdr'); bot=OxmlElement('w:bottom')
bot.set(qn('w:val'),'single'); bot.set(qn('w:sz'),'18'); bot.set(qn('w:space'),'1'); bot.set(qn('w:color'),'D4A530')
pbdr.append(bot); pPr.append(pbdr)

def para(space_after=6, before=0):
    p=doc.add_paragraph(); pf=p.paragraph_format
    pf.space_after=Pt(space_after); pf.space_before=Pt(before); pf.line_spacing=1.12
    return p
def run(p,text,color=DARK,italic=False,bold=False,font=BODYF,size=10.0):
    r=p.add_run(text); setfont(r,font); r.font.size=Pt(size); r.font.color.rgb=color
    r.italic=italic; r.bold=bold; return r

# recipient
rp=para(2); run(rp,"21 October 2026",color=DARK,bold=True,font=HEADF,size=9.5)
rp2=para(1); run(rp2,"Appointment committee · PhD Research Fellow, TRANSPLAN",color=DARK,bold=True,font=HEADF,size=10)
rp3=para(12); run(rp3,"Jobbnorge 308701 · Department of Logistics, Molde University College",color=MUT,font=HEADF,size=9.5)

sal=para(7); run(sal,"Dear members of the committee,",size=11)

p=para(); run(p,"I am applying for the TRANSPLAN fellowship with the proposal "); run(p,"From end states to pathways",italic=True); run(p,", which I have already started building. The call says the proposal is the most important criterion, so this letter is short and points to the evidence there.")

p=para(); run(p,"I am a mechanical engineer finishing an MSc in Sustainable Energy Logistics at HiMolde (2024 to 2026). Before the master I spent four years in cross-border procurement and freight logistics across the DACH region, India and the UAE. The engineering gave me systems and optimisation; the procurement years gave me the freight side the proposal leans on, including how carriers actually weigh road against sea.")

p=para(); run(p,"The method is already under construction, not only described. The pipeline runs end to end in a public repository with "); run(p,"89 tests",color=GOLD,bold=True); run(p,", and two real road networks, Kristiansund and Molde, are already benchmarked. Before trusting that pipeline on data I will estimate myself, I checked it against a known answer: a published mixed logit on Swissmetro, reproduced in Biogeme to the fourth decimal, "); run(p,"−5214.9 against −5214.8",color=GOLD,bold=True); run(p,". That is the machinery the acceptance estimation runs on. The estimation itself is the thesis.")

p=para(); run(p,"The layer sits beside the national models, not over them. It is the dynamic, acceptance-based layer that TØI 1819/2021 asked for and that "); run(p,"Veivalg",italic=True); run(p," (TØI 2172/2026) argues TRANSPLAN needs for pricing and capacity. Freight is estimated, not bolted on: Kristiansund’s live Bypakke toll, Molde as the no-toll control, and the Ferjefri E39 corridor where the freight signpost should fire first. If the carrier sample is thin it stands on national elasticities, so the result holds either way. Acceptance enters as an admissibility condition, "); run(p,"λ",color=GOLD,bold=True); run(p,", inside a robust min-max-regret search over pricing pathways to 2050, not a survey reported after the model has run.")

p=para(); run(p,"This is not my first novel computational build. My MSc thesis produced a verifiable crypto-erasure method for cross-border audit trails, which I presented at NORS 2025. The subject differs; the discipline, a tested artefact for a real policy problem, is the same.")

p=para(); run(p,"The work is scoped as three articles at "); run(p,"months 12, 24 and 30",color=GOLD,bold=True); run(p,", inside the three years. The supervision it needs, discrete choice, robustness and freight, is resident in this department, which is part of why I am applying here. The survey instrument is drafted in English and piloted with Norwegian-speaking co-authors.")

p=para(8); run(p,"Enclosed are the five-page proposal, my CV, diplomas and transcripts, my MSc thesis abstract, and three referees. I would welcome an interview to discuss the estimation and the three-year plan.")

sp=para(1); run(sp,"Yours sincerely,",size=11)
sn=para(0); run(sn,"Arshad Akhtar Abbasia, Molde",bold=True,font=HEADF,size=11)

doc.save("From-end-states-to-pathways_cover-letter.docx")
print("docx saved")
# em dash guard
import zipfile,re
x=zipfile.ZipFile("From-end-states-to-pathways_cover-letter.docx").read("word/document.xml").decode("utf-8")
print("em dashes in docx:", x.count("—"))
