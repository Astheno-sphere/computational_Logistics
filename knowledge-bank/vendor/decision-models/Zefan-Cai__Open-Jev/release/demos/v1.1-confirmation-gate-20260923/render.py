#!/usr/bin/env python3
"""CPU-only 32-second replay of two audited predictions. No model or network calls.
Requires Pillow and ffmpeg/ffprobe. Run in this directory: python render.py
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json,math,subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
E=json.loads((ROOT/'evidence.json').read_text())
W,H,FPS,DURATION=1280,720,30,32
BG='#f3f3ee';INK='#132d35';MUTED='#4f676e';LINE='#d8e1dc';TEAL='#067d70';PALE='#e1f2e9';RED='#b34438';PINK='#fae6df';WHITE='#ffffff';BLUE='#2563eb'
ORDER=E['display_order'];NAMES=E['aliases']

def font_path(bold=False):
    names=(['/System/Library/Fonts/Supplemental/Arial Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold else ['/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    return next(x for x in names if Path(x).is_file())

@lru_cache(maxsize=40)
def font(size,bold=False):return ImageFont.truetype(font_path(bold),size)

def text(d,xy,s,size=20,fill=INK,bold=False):d.text(xy,str(s),font=font(size,bold),fill=fill)
def box(d,xy,fill=WHITE,outline=None,r=18,width=1):d.rounded_rectangle(xy,radius=r,fill=fill,outline=outline,width=width)
def lines(d,xy,s,size=22,fill=MUTED,bold=False,spacing=8):
    for i,line in enumerate(s.split('\n')):text(d,(xy[0],xy[1]+i*(size+spacing)),line,size,fill,bold)
def pill(d,x,y,s,fill=PALE,ink=TEAL,size=15):
    width=round(font(size,True).getlength(s))+24;box(d,(x,y,x+width,y+30),fill,r=15);text(d,(x+12,y+6),s,size,ink,True);return width

def base():
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    box(d,(40,23,75,58),INK,r=10);text(d,(48,29),'J',24,WHITE,True)
    text(d,(90,29),'Open-Jev-27B-v1.1',23,INK,True)
    text(d,(742,34),'RECORDED MODEL OUTPUTS  /  EDITED PLAYBACK',15,MUTED,True)
    d.line((40,77,1240,77),fill=LINE,width=1)
    text(d,(42,664),'Illustrative UI from synthetic text-state records. No browser actions executed.',17,MUTED)
    text(d,(42,689),'Model probabilities are not accuracy. Source records and complete distributions accompany the demo.',15,MUTED)
    return im

def fact(d,x,y,label,value,bad=False):
    text(d,(x,y),label,16,MUTED,True);text(d,(x,y+27),value,31,RED if bad else INK,True)

def option_card(d,x,y,width,which='item_63',changed=False,small=False):
    bad=which=='item_63' and changed;h=208 if not small else 145
    box(d,(x,y,x+width,y+h),PINK if bad else WHITE,RED if bad else LINE,width=2 if bad else 1)
    text(d,(x+22,y+18),f'{NAMES[which]}  ({which})',22,INK,True)
    label='Target mismatch' if bad else 'All 4 requirements met'
    pill(d,x+22,y+54,label,PINK if bad else PALE,RED if bad else TEAL,14)
    if small:
        text(d,(x+22,y+100),'73 interactions' if which=='item_63' else '75 interactions',18,MUTED)
        return
    fact(d,x+22,y+100,'PREVIEW TARGET','record_A')
    text(d,(x+224,y+130),'→',32,MUTED)
    fact(d,x+270,y+100,'ACTUAL TARGET','record_B' if bad else 'record_A',bad)
    text(d,(x+22,y+177),'73 interactions' if which=='item_63' else '75 interactions',17,MUTED)

def probability_panel(d,variant):
    c=E['cases'][variant];p=dict(zip(c['record']['options'],c['prediction']['probabilities']));winner=max(p,key=p.get)
    box(d,(724,205,1240,626),WHITE,LINE)
    text(d,(748,225),'RECORDED MODEL DISTRIBUTION',16,MUTED,True)
    pill(d,748,257,f'Selected: {NAMES[winner]} ({winner})')
    for i,key in enumerate(ORDER):
        y=304+i*40;v=p[key];selected=key==winner;color=TEAL if selected else MUTED
        label=NAMES[key] if key=='abstain' else f'{NAMES[key]} ({key})'
        text(d,(748,y),label,18,color,selected)
        val=f'{v*100:.2f}%' if v*100>=0.01 else '<0.01%'
        text(d,(1151,y),val,18,color,selected)
        box(d,(960,y+4,1133,y+17),'#e7eeea',r=5)
        if v>0:box(d,(960,y+4,960+max(2,173*v),y+17),TEAL if selected else '#9eb6ac',r=4)
    text(d,(748,593),'All 6 options + abstain · display order aligned',14,MUTED)

def intro():
    im=base();d=ImageDraw.Draw(im)
    pill(d,44,106,'A SMALL CHECK BEFORE AN ACTION')
    lines(d,(42,168),'Same preview.\nDifferent target.',68,INK,True,9)
    lines(d,(46,348),'Would you still choose\nthe same option?',28,MUTED,False,9)
    text(d,(46,467),'Two actual 27B v1.1 predictions.',23,TEAL,True)
    text(d,(46,505),'A new visual replay of audited OOD records.',20,MUTED)
    box(d,(761,139,1238,601),WHITE,LINE)
    text(d,(788,168),'OPTION A (item_63)',19,MUTED,True)
    fact(d,790,229,'PREVIEW TARGET','record_A')
    d.line((790,321,1207,321),fill=LINE,width=1)
    fact(d,790,352,'ACTUAL TARGET CHANGES','record_A  →  record_B',False)
    pill(d,790,452,'The preview stays the same.',PINK,RED,17)
    text(d,(790,524),'A comparison of saved text states.',17,MUTED)
    return im

def case(variant):
    im=base();d=ImageDraw.Draw(im)
    text(d,(44,102),f'CASE 0{variant+1} / '+('MATCHING TARGET' if variant==0 else 'CHANGED TARGET'),17,TEAL,True)
    text(d,(42,139),'The preview matches.' if variant==0 else 'The target no longer matches.',43,INK,True)
    option_card(d,42,205,650,changed=bool(variant))
    option_card(d,42,431,650,which='K11',small=True)
    text(d,(43,595),'Policy: confirm if required · target match · active session · revision match',16,MUTED)
    text(d,(43,620),'Tie-break: choose the fewest interactions among eligible options.',17,MUTED)
    probability_panel(d,variant)
    return im

def change():
    im=base();d=ImageDraw.Draw(im)
    pill(d,43,102,'COMPARE THE SAVED INPUTS',PINK,RED)
    text(d,(42,152),'Keep the preview. Change the target.',47,INK,True)
    option_card(d,42,235,579,changed=False)
    option_card(d,660,235,579,changed=True)
    text(d,(64,472),'Original state',20,TEAL,True);text(d,(682,472),'Counterfactual state',20,RED,True)
    text(d,(44,538),'Only one candidate fact changes: item_63.actual_target.',25,INK,True)
    text(d,(44,582),'The recorded option order also differs; original orders are preserved in the evidence.',19,MUTED)
    return im

def compare():
    im=base();d=ImageDraw.Draw(im)
    text(d,(44,104),'TWO RECORDED CASES',17,TEAL,True)
    text(d,(42,145),'Same preview. A different selection.',47,INK,True)
    for x,v in [(42,0),(660,1)]:
        c=E['cases'][v];p=dict(zip(c['record']['options'],c['prediction']['probabilities']));winner=max(p,key=p.get)
        box(d,(x,238,x+578,560),WHITE,LINE)
        text(d,(x+26,263),'TARGET MATCHES' if v==0 else 'TARGET CHANGED',17,TEAL if v==0 else RED,True)
        text(d,(x+26,309),'Preview: record_A',25,INK,True)
        text(d,(x+26,350),'Actual:   '+('record_A' if v==0 else 'record_B'),25,INK if v==0 else RED,True)
        d.line((x+26,399,x+550,399),fill=LINE,width=1)
        text(d,(x+26,423),f'{NAMES[winner]} ({winner})',28,TEAL,True)
        text(d,(x+26,468),f'{p[winner]*100:.2f}% model probability',23,MUTED)
        text(d,(x+26,513),'73 < 75 interactions' if v==0 else 'Option A fails the target-match rule.',17,MUTED)
    text(d,(43,598),'The model selects an option. It does not execute the browser action.',22,INK)
    return im

def end():
    im=base();d=ImageDraw.Draw(im)
    box(d,(42,108,1238,628),INK,r=23)
    pill(d,74,140,'OPEN MODEL · OPEN CODE · OPEN DATA',fill='#25484f',ink='#bce6cd',size=16)
    lines(d,(74,210),'Inspect the decision.\nBuild your own.',61,WHITE,True,8)
    text(d,(77,385),'Open-Jev-27B-v1.1',30,'#bce6cd',True)
    text(d,(77,451),'zefan-cai.github.io/open-jev/',30,WHITE,True)
    text(d,(77,513),'Full inputs, logits, probabilities and provenance with this replay.',21,'#c1d2cf')
    text(d,(77,554),'Selected synthetic examples · no general task-success claim',18,'#c1d2cf')
    return im

SCENES=[(0,intro),(3,lambda:case(0)),(11,change),(15,lambda:case(1)),(24,compare),(29,end)]
@lru_cache(maxsize=6)
def scene(i):return SCENES[i][1]()

def frame(t):
    i=max(j for j,(start,_) in enumerate(SCENES) if t>=start)
    im=scene(i).copy();elapsed=t-SCENES[i][0]
    if i and elapsed<.28:im=Image.blend(scene(i-1),im,elapsed/.28)
    d=ImageDraw.Draw(im);d.rectangle((0,715,int(W*t/DURATION),719),fill=TEAL)
    return im

CUES=[(0,3,'Same preview. Different target. A replay of actual Open-Jev-27B-v1.1 predictions.'),(3,7,'Option A and Option B both satisfy the four visible requirements.'),(7,11,'Fewer interactions wins. Recorded selection: Option A (item_63), 99.42% model probability.'),(11,15,'Option A now targets record_B; its preview remains record_A. Recorded option order also differs.'),(15,20,'Option A no longer meets the target-match rule. All other candidate facts are unchanged.'),(20,24,'The second recorded choice is Option B, K11, at 95.62 percent model probability.'),(24,29,'These are two selected synthetic text-state cases. No browser actions were executed. Edited playback is not inference latency.'),(29,32,'Open-Jev-27B-v1.1. Inspect the evidence. Model, code and data are linked.')]
def ts(t):return f'00:00:{t:02d}.000'

def main():
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(ROOT/'replay.mp4')]
    p=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for n in range(FPS*DURATION):p.stdin.write(frame(n/FPS).tobytes())
        p.stdin.close();assert p.wait()==0
    except BaseException:p.kill();p.wait();raise
    scene(0).save(ROOT/'poster.png');scene(0).save(ROOT/'poster.jpg',quality=95,optimize=True)
    sheet=Image.new('RGB',(1920,720),BG)
    for i,t in enumerate([1,7,12,20,26,30]):
        shot=frame(t);shot.save(ROOT/f'frame-{t:02d}.png');sheet.paste(shot.resize((640,360)),((i%3)*640,(i//3)*360))
    sheet.save(ROOT/'contact-sheet.jpg',quality=94,optimize=True)
    (ROOT/'captions.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{ts(a)} --> {ts(b)}\n{s}' for a,b,s in CUES)+'\n')
    (ROOT/'script.md').write_text('# Same preview. Different target.\n\nA 32-second, silent English replay of actual Open-Jev-27B-v1.1 outputs. No new inference or browser actions.\n\n'+'\n\n'.join(f'**{a}–{b}s:** {s}' for a,b,s in CUES)+'\n\nThe two options arrays are retained exactly. Stable display aliases align the charts for reading and do not change model inputs. All six options and abstention are visible. Visible rule explanations come from the supplied policy; they are not model-generated reasoning.\n')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height,pix_fmt,r_frame_rate:format=duration','-of','json',str(ROOT/'replay.mp4')],text=True))
    assert len(probe['streams'])==1 and probe['streams'][0]['codec_name']=='h264' and probe['streams'][0]['pix_fmt']=='yuv420p';assert float(probe['format']['duration'])==DURATION
    raw=(ROOT/'replay.mp4').read_bytes();assert raw.index(b'moov')<raw.index(b'mdat')
    result={'status':'rendered','duration_seconds':DURATION,'fps':FPS,'width':W,'height':H,'codec':'h264','pixel_format':'yuv420p','audio':False,'faststart':True,'model_inference_performed':False,'browser_actions_executed':False,'fonts':[font_path(),font_path(True)],'files':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(ROOT.iterdir()) if p.is_file() and p.name not in ['render-receipt.json']}}
    (ROOT/'render-receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'rendered','video_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}))

if __name__=='__main__':main()
