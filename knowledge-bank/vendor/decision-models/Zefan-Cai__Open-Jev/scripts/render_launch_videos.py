"""Render social-video drafts from reviewed, saved model outputs. No inference."""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'release/social'
FPS, W, H = 24, 1280, 720
BG, INK, GREEN, MUTED, PANEL = '#f5f4ef', '#102d28', '#14785b', '#526a63', '#e8eee5'
FONTS = Path('/System/Library/Fonts/Supplemental')

def font(size, bold=False):
    options = [FONTS / ('Arial Bold.ttf' if bold else 'Arial.ttf'),
               Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    return ImageFont.truetype(str(next(p for p in options if p.exists())), size)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(seconds):
    value = round(seconds * 1000)
    return f'{value//3600000:02d}:{value//60000%60:02d}:{value//1000%60:02d}.{value%1000:03d}'


CAT = json.loads((ROOT / 'site/catalog.json').read_text())
ITEMS = {item['id']: item for item in CAT['items']}
for ident in ('customer-workflow', 'painting-palette', 'reasoning-arithmetic'):
    assert ITEMS[ident]['showcase_review']['status'] == 'success'

SCENES = {
    'brand': (6, 'Open-Jev · open Qwen-based decision models.'),
    'interface': (8, 'Context + candidates → typed probabilities.'),
    'demo-title': (5, 'Selected successful demos. Complete game episodes.'),
    'customer': (10, 'Saved model: do not cancel (99.995%).'),
    'painting': (10, '64 saved decisions → a complete 8×8 image.'),
    'arithmetic': (10, 'Saved model: 57 (99.996%).'),
    'outro': (8, 'Open code, models and task data. Inspired by Jev.'),
}


def frame(scene, t, duration):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((60, 30), '[J]  Open-Jev', font=font(28, True), fill=INK)
    d.line((60, 82, 1220, 82), fill='#cad7cd', width=2)
    def text(pos, value, size=32, color=INK, bold=False):
        d.multiline_text(pos, value, font=font(size, bold), fill=color, spacing=12)
    def panel():
        d.rounded_rectangle((700, 160, 1215, 592), 26, fill=PANEL)
    def label(value):
        text((64, 111), value.upper(), 22, GREEN, True)
    if scene in ('brand', 'demo-title'):
        label('Open decision models' if scene == 'brand' else 'Selected successful examples')
        text((64, 203), 'Turn context\ninto decisions.' if scene == 'brand' else 'See what\nthe model decides.', 76, bold=True)
        text((68, 424), 'Built on Qwen  ·  2B & 9B', 34, MUTED)
        text((68, 493), 'Choice    /    Noul    /    Score' if scene == 'brand' else 'Real saved outputs. Complete game episodes.', 27, GREEN)
        d.rounded_rectangle((940, 206, 1178, 444), 34, fill=INK)
        text((975, 253), '[J]', 114, '#bcf3cf', True)
    elif scene == 'interface':
        label('One decision interface')
        text((64, 178), 'Your context.\nYour candidates.', 61, bold=True)
        text((66, 350), 'Direct probabilities.\nNo generated text to parse.', 31, MUTED)
        panel()
        rows=[('Choice', 'Pick from supplied candidates'), ('Noul', 'Estimate a yes/no probability'), ('Score', 'Score an ordered criterion')]
        for n,(a,b) in enumerate(rows):
            y=196+n*122
            text((727,y),a,38,GREEN,True)
            text((729,y+51),b,22,MUTED)
        text((67, 523), 'One shared model across task domains.', 28, GREEN)
    elif scene == 'customer':
        label('Customer support · saved 9B full-pass output')
        text((64, 172), 'Keep the account\nas it is.', 58, bold=True)
        text((68, 335), '“Everything is resolved.\nThank you.”', 34, MUTED)
        text((68, 456), 'Policy: cancel only with an explicit\nrequest and matching consent.', 26, MUTED)
        panel()
        text((739, 204), 'Cancel subscription?', 31)
        if t >= 1.5:
            text((739, 291), 'NO', 94, GREEN, True)
            p=1-ITEMS['customer-workflow']['answer']['probabilities'][1]
            text((742, 425), f'{p:.3%}', 48, GREEN, True)
            text((744, 491), 'Saved model probability', 23, MUTED)
    elif scene == 'painting':
        label('Pixel decisions · saved 9B full-pass output')
        text((64, 166), 'A description.\n64 color decisions.', 56, bold=True)
        text((68, 325), 'Yellow rectangle.\nRed background.', 34, MUTED)
        text((68, 438), '8 × 8 canvas\nDrawn from saved model outputs.', 27, MUTED)
        pixels=ITEMS['painting-palette']['pixel_predictions']
        count=min(64, math.floor(max(0,t-1)*64/5))
        for n,p in enumerate(pixels):
            x,y=735+p['x']*55,166+p['y']*55
            d.rounded_rectangle((x,y,x+52,y+52),4,fill=tuple(p['rgb']) if n<count else '#dae4d9')
        text((744, 617), f'{count:02d} / 64 pixels', 23, GREEN, True)
    elif scene == 'arithmetic':
        label('Reasoning · saved 9B full-pass output')
        text((64, 174), 'Choose the\nexact result.', 60, bold=True)
        text((68, 366), '(34 − 15) × 3', 49, GREEN, True)
        text((68, 462), 'Four supplied candidates.\nOne probability distribution.', 27, MUTED)
        probabilities=ITEMS['reasoning-arithmetic']['answer']['probabilities']
        for n,(number,p) in enumerate(zip((54,57,62,50), probabilities)):
            y=181+n*105
            d.rounded_rectangle((703,y,1213,y+88),16,fill='#d6ecd9' if n==1 and t>=1.5 else PANEL)
            text((726,y+21),str(number),36, GREEN if n==1 else INK,True)
            if t>=1.5:text((933,y+25),f'{p:.3%}',29,GREEN if n==1 else MUTED,n==1)
    elif scene == 'outro':
        label('Open code · models · task data')
        text((64, 167), 'Explore Open-Jev.', 70, bold=True)
        text((70, 306), 'github.com/Zefan-Cai/Open-Jev', 36, GREEN, True)
        text((70, 389), 'zefan-cai.github.io/open-jev/', 34, MUTED)
        text((70, 495), 'Independent implementation inspired by Jev.', 26, MUTED)
    footer='Saved outputs · selected examples · playback is not inference latency' if scene in ('customer','painting','arithmetic') else 'Open-Jev · research release'
    text((64, 673), footer, 18, MUTED)
    d.rectangle((0,711,round(W*min(1,t/duration)),719),fill=GREEN)
    return im


def render_scene(scene, path):
    duration=SCENES[scene][0]
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
             '-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-g','48','-an','-movflags','+faststart',str(path)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for i in range(duration*FPS):process.stdin.write(frame(scene,i/FPS,duration).tobytes())
        process.stdin.close()
        if process.wait():raise RuntimeError('Video encoding failed')
    except BaseException:
        process.kill();process.wait();raise


def compose(name, scenes, clips, target):
    listing=target/(name+'.concat')
    listing.write_text(''.join("file '"+str(clips[scene]).replace("'","'\\''")+"'\n" for scene in scenes))
    output=OUT/(name+'.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),
                    '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r','24','-g','48','-an','-movflags','+faststart',str(output)],check=True)
    cursor=0;chapters=[];cues=[]
    gameplay=json.loads((ROOT/'site/media/gameplay-verification.json').read_text())
    for scene in scenes:
        if scene=='games':
            duration=gameplay['overview']['duration_seconds']
            for chapter in gameplay['overview']['chapters']:
                chapters.append({**chapter,'start_seconds':cursor+chapter['start_seconds'],'end_seconds':cursor+chapter['end_seconds']})
            # Preserve all native captions at their chapter-relative times.
            for block in (ROOT/'site/media/gameplay-overview.vtt').read_text().split('\n\n')[1:]:
                if '-->' not in block:continue
                timing,caption=block.strip().split('\n',1)
                def seconds(v):
                    h,m,s=v.split(':');return int(h)*3600+int(m)*60+float(s)
                a,b=timing.split(' --> ');cues.append((cursor+seconds(a),cursor+seconds(b),caption))
        else:
            duration,caption=SCENES[scene]
            chapters.append({'id':scene,'start_seconds':cursor,'end_seconds':cursor+duration})
            cues.append((cursor,cursor+duration,caption))
        cursor+=duration
    (OUT/(name+'.vtt')).write_text('WEBVTT\n\n'+'\n\n'.join(f'{stamp(a)} --> {stamp(b)}' + (' line:85% position:3% align:start size:44%' if c in {v[1] for v in SCENES.values()} else '') + f'\n{c}' for a,b,c in cues)+'\n')
    (OUT/(name+'.txt')).write_text('\n\n'.join(c for _,_,c in cues)+'\n')
    frame(scenes[0],3,SCENES[scenes[0]][0]).save(OUT/(name+'.jpg'),quality=95)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],text=True))
    stream=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert abs(float(probe['format']['duration'])-cursor)<.05
    assert int(stream['nb_frames'])==round(cursor*FPS)
    assert cursor<140 and stream['codec_name']=='h264' and stream['pix_fmt']=='yuv420p'
    return {'path':str(output.relative_to(ROOT)),'sha256':sha(output),'duration_seconds':float(probe['format']['duration']),
            'frames':int(stream['nb_frames']),'chapters':chapters,'draft':True,'new_inference':False,'outcome_selected':True}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='openjev-launch-') as name:
        temp=Path(name);clips={}
        for scene in SCENES:
            path=temp/(scene+'.mp4');render_scene(scene,path);clips[scene]=path
        clips['games']=ROOT/'site/media/gameplay-overview.mp4'
        intro=compose('open-jev-introduction',['brand','interface','customer','painting','arithmetic','outro'],clips,temp)
        demos=compose('open-jev-demos',['demo-title','customer','painting','arithmetic','games','outro'],clips,temp)
    evidence={'status':'rendered_pending_browser_review','renderer_sha256':sha(Path(__file__)),'catalog_sha256':sha(ROOT/'site/catalog.json'),
              'sources':{key:ITEMS[key]['showcase_review'] for key in ('customer-workflow','painting-palette','reasoning-arithmetic')},
              'gameplay_manifest_sha256':sha(ROOT/'site/media/gameplay-verification.json'),'videos':[intro,demos],
              'scope':'Draft promotional presentation. Actual saved 9B full-pass outputs for non-game examples; original 9B pilot actions for full game episodes. No new inference. Selected successes, not general task-success or speed evidence.'}
    (OUT/'video-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'videos':[{'path':x['path'],'seconds':x['duration_seconds']} for x in evidence['videos']]}))


if __name__=='__main__':main()
