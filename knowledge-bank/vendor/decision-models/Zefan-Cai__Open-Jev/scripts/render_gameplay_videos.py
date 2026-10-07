#!/usr/bin/env python3
"""Render complete, verified local-game episodes as continuous gameplay videos.

CPU only. Requires Pillow, ffmpeg and ffprobe. No model, network or GPU calls.
Every recorded action is re-executed through jev.games.replay_episode before any
video is rendered. Smooth motion interpolates verified states; the box runner's
movement follows its existing collision-simulation equations. These original
Python games have no native GUI, so this file supplies their game canvas. It
does not depict a commercial game or a new model rollout.

    python scripts/render_gameplay_videos.py
    python scripts/render_gameplay_videos.py --verify-only
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jev.game_cli import _game
from jev.games import replay_episode

W, H, FPS = 1280, 720, 24
INTRO, OUTRO = 3.0, 5.0
BG, INK, MUTED = '#081b24', '#f5f3e9', '#a4bfc5'
MINT, CORAL, GOLD = '#b0f5d1', '#fc8d86', '#f6cd80'
TRACE_DIR = ROOT/'reports/pilot-suite-n1-4k/9b/games/trajectories'
SPECS = {
    'snake': {'file': 'snake', 'title': 'SNAKE', 'goal': 'Eat the coral food. Avoid the walls and your own body.',
              'seconds_per_action': 1.8, 'outcome': 'WALL COLLISION', 'result': 'Goal not reached · 0 food collected'},
    'platformer': {'file': 'tile_platformer', 'title': 'TILE PLATFORMER', 'goal': 'Reach the gold flag without falling into a gap.',
                   'seconds_per_action': .7, 'outcome': 'FLAG NOT REACHED', 'result': '40 decisions · 0 tiles gained · action limit reached'},
    'trex': {'file': 'trex_runner', 'title': 'BOX RUNNER', 'goal': 'Clear all 12 obstacles without a collision.',
             'seconds_per_action': 2.6, 'outcome': 'ALL OBSTACLES CLEARED', 'result': 'Goal reached · 12 / 12 obstacles cleared'},
    'wiki': {'file': 'wikiracing', 'title': 'WIKI-RACING', 'goal': 'Go from Computer to Physics by following article links.',
             'seconds_per_action': 4.5, 'outcome': 'TARGET REACHED', 'result': 'Computer → Mathematics → Physics · 2 links'},
}


@lru_cache(maxsize=25)
def font(size):
    for path in ('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', '/System/Library/Fonts/Helvetica.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError('Install Arial Unicode, Helvetica or DejaVu Sans')


def text(d, x, y, s, size=22, color=INK):
    d.text((x, y), str(s), font=font(size), fill=color)


def centered(d, y, s, size=30, color=INK):
    text(d, (W-font(size).getlength(s))/2, y, s, size, color)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ease(t):
    t = max(0.0, min(1.0, t))
    return t*t*(3-2*t)


def lerp(a, b, t):
    return a+(b-a)*t


def source_trace(key):
    path = TRACE_DIR/f"{SPECS[key]['file']}-model-seed-10001.json"
    return path, json.loads(path.read_text())


def moment(trace, spec, t):
    step_seconds = spec['seconds_per_action']
    elapsed = max(0, t-INTRO)
    index = min(len(trace['steps'])-1, int(elapsed/step_seconds))
    local = min(1.0, (elapsed-index*step_seconds)/step_seconds)
    finished = t >= INTRO+len(trace['steps'])*step_seconds
    step = trace['steps'][index]
    return index, local, finished, step


def duration(trace, spec):
    return math.ceil((INTRO+len(trace['steps'])*spec['seconds_per_action']+OUTRO)*FPS)/FPS


@lru_cache(maxsize=4)
def background(key):
    im = Image.new('RGB', (W,H), BG)
    d = ImageDraw.Draw(im)
    if key in ('platformer', 'trex'):
        # Original decorative scenery, separate from collision geometry.
        d.rectangle((0, 123, W, 645), fill='#102c39')
        for cx,cy,r in ((104,189,2),(357,240,2),(985,197,2),(1160,322,2),(622,213,2)):
            d.ellipse((cx-r,cy-r,cx+r,cy+r), fill='#31535e')
        for offset in (0,350,700,1050):
            d.polygon(((offset-100,560),(offset+175,310),(offset+450,560)), fill='#153b48')
    d.line((40,116,1240,116),fill='#31505a',width=1)
    d.line((40,675,1240,675),fill='#31505a',width=1)
    return im


def hud(d, key, trace, spec, t, index, local, finished):
    text(d, 42, 22, spec['title'], 31, MINT)
    text(d, 42, 71, 'GOAL  '+spec['goal'], 23)
    text(d, 950, 24, 'Qwen3.5-9B · pilot', 20, MUTED)
    text(d, 950, 55, 'Complete recorded episode', 16, MUTED)
    label = 'READY' if t < INTRO else f"{index+1:02d} / {len(trace['steps']):02d}"
    if key == 'snake':
        score=sum(s['reward']>0 for s in trace['steps'][:index+(local>=1 or finished)])
        text(d, 66, 153, f'FOOD  {score}', 25, MINT)
        text(d, 66, 193, f'MOVES  {label}', 19, MUTED)
    elif key == 'platformer':
        player=(trace['steps'][index]['next_state'] if finished else trace['steps'][index]['request']['state'])['player']
        text(d, 54, 143, f"PROGRESS  {player['x']-2} / 44 tiles", 22, MINT)
        text(d, 994, 143, f'DECISION {label}', 18, MUTED)
    elif key == 'trex':
        cleared=index if not finished else trace['metrics']['obstacles_cleared']
        text(d, 54, 143, f'CLEARED  {cleared} / 12', 23, MINT)
        text(d, 994, 143, f'OBSTACLE {label}', 18, MUTED)
    else:
        text(d, 54, 143, f'LINKS FOLLOWED  {index if not finished else len(trace["steps"])}', 21, MINT)
    action = trace['steps'][index]['action'].replace('_',' ').upper()
    if t>=INTRO and not finished:
        if key=='snake':
            text(d, 66, 249, 'ACTION', 16, MUTED)
            text(d, 66, 278, action, 27)
        else:
            text(d, 520, 144, 'ACTION  '+action, 21, INK)
    footer = 'Original local game · verified action replay · seed 10001 · motion timing adjusted'
    text(d, 42, 687, footer, 16, MUTED)


def end_overlay(im, spec, success):
    layer=Image.new('RGBA',im.size,(0,0,0,0))
    d=ImageDraw.Draw(layer)
    d.rounded_rectangle((158,262,1122,457),22,fill=(4,18,26,236),outline=MINT if success else CORAL,width=3)
    color=MINT if success else CORAL
    width=font(40).getlength(spec['outcome'])
    text(d,(W-width)/2,290,spec['outcome'],40,color)
    width=font(27).getlength(spec['result'])
    text(d,(W-width)/2,356,spec['result'],27,INK)
    text(d,467,409,'End of the complete saved episode',18,MUTED)
    return Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')


def snake_canvas(d, trace, t, index, local, finished):
    step=trace['steps'][index]
    before=step['request']['state']
    after=step['next_state']
    x0,y0,cell=378,133,86
    for y in range(6):
        for x in range(6):
            d.rounded_rectangle((x0+x*cell,y0+y*cell,x0+(x+1)*cell-3,y0+(y+1)*cell-3),7,fill='#173b45' if (x+y)%2==0 else '#14343f')
    d.rounded_rectangle((x0-5,y0-5,x0+6*cell+2,y0+6*cell+2),9,outline=CORAL if finished else '#507881',width=3)
    food=before['food']
    fx,fy=x0+(food[0]+.5)*cell,y0+(food[1]+.5)*cell
    d.ellipse((fx-20,fy-20,fx+20,fy+20),fill=CORAL)
    d.ellipse((fx-11,fy-13,fx-3,fy-5),fill='#ffd7b6')
    ratio=0 if t<INTRO else ease(min(1,local/.75))
    points=[]
    for n,point in enumerate(before['snake_head_first']):
        target=after['snake_head_first'][min(n,len(after['snake_head_first'])-1)]
        points.append((x0+(lerp(point[0],target[0],ratio)+.5)*cell,y0+(lerp(point[1],target[1],ratio)+.5)*cell))
    if len(points)>1:
        d.line(points,fill='#70beaa',width=cell-19)
    for n,(px,py) in reversed(list(enumerate(points))):
        d.rounded_rectangle((px-33,py-33,px+33,py+33),15,fill=MINT if n==0 else '#70beaa')
    hx,hy=points[0]
    direction=before['direction'] if t<INTRO else step['action']
    dx,dy={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}[direction]
    for side in (-1,1):
        ex,ey=hx+dx*17-dy*side*12,hy+dy*17+dx*side*12
        d.ellipse((ex-4,ey-4,ex+4,ey+4),fill=BG)
    if step['terminal'] and local>.55:
        wall_x=x0+6*cell
        d.line((wall_x,hy-34,wall_x,hy+34),fill=CORAL,width=9)
        text(d,954,365,'WALL HIT',23,CORAL)
    if t<INTRO:
        text(d,967,225,'FOOD',18,CORAL)
        text(d,967,260,'Coral dot',20,MUTED)
        text(d,967,323,'PLAYER',18,MINT)
        text(d,967,358,'Mint snake',20,MUTED)


def platformer_canvas(d, trace, t, index, local, finished):
    step=trace['steps'][index]
    before,after=step['request']['state'],step['next_state']
    ratio=0 if t<INTRO else ease(min(1,local/.8))
    a,b=before['player'],after['player']
    px,py=lerp(a['x'],b['x'],ratio),lerp(a['y'],b['y'],ratio)
    columns=before['terrain']['columns']
    cell,ground,x0=48,559,54
    start=max(0,min(24,int(px)-4))
    for x in range(start,min(len(columns),start+24)):
        floor=columns[x]
        sx=x0+(x-start)*cell
        if floor is None:
            d.rectangle((sx,ground,sx+cell,611),fill='#071b28')
            continue
        top=ground-floor*cell
        d.rectangle((sx,top,sx+cell-1,611),fill='#244e54')
        d.rectangle((sx,top,sx+cell-1,top+5),fill='#82c3a0')
        d.line((sx+2,top+8,sx+2,611),fill='#305e60')
    player_x=x0+(px-start)*cell+5
    player_y=ground-py*cell-41
    d.rounded_rectangle((player_x,player_y,player_x+37,player_y+40),6,fill=MINT)
    d.rectangle((player_x+23,player_y+10,player_x+28,player_y+16),fill=BG)
    flag=before['terrain']['flag_x']
    if start<=flag<start+24:
        fx=x0+(flag-start)*cell
        d.line((fx,ground-110,fx,ground),fill=GOLD,width=4)
        d.polygon(((fx,ground-110),(fx+55,ground-91),(fx,ground-72)),fill=GOLD)
    else:
        text(d,971,233,f'FLAG  {flag-int(px)} tiles →',24,GOLD)
    # Whole-level minimap preserves context when the view follows the player.
    for x,floor in enumerate(columns):
        sx=66+x*23
        if floor is not None:d.rectangle((sx,640-floor*3,sx+21,648),fill='#558b83')
    d.ellipse((66+px*23-5,622,66+px*23+5,632),fill=MINT)
    d.rectangle((66+flag*23,620,66+flag*23+5,647),fill=GOLD)
    text(d,55,594,'LEVEL MAP',13,MUTED)


def runner_motion(state, action, phase):
    """Same launch timing, velocity, gravity and coordinates as trex_collision."""
    obstacle,geometry=state['target_obstacle'],state['runner_geometry']
    speed=state['current_speed']/20
    start=geometry['obstacle_start_x']
    width=geometry['player_width']
    velocity,gravity=(.48,.08) if action=='jump_short' else (.8,.06)
    midpoint=(start+(obstacle['width']-width)/2)/speed
    launch=max(0,midpoint-velocity/gravity)
    end=(start+obstacle['width'])/speed
    tick=phase*end
    x=start-speed*tick
    elapsed=max(0,tick-launch)
    bottom=max(0,velocity*elapsed-gravity*elapsed*elapsed/2) if action.startswith('jump_') else 0
    height=geometry['duck_height'] if action=='duck' else geometry['standing_height']
    return x,bottom,height


def trex_canvas(d,trace,t,index,local,finished):
    step=trace['steps'][index]
    state=step['request']['state']
    phase=0 if t<INTRO else min(1,local)
    if finished:phase=1
    ox,bottom,height=runner_motion(state,step['action'],phase)
    units,player_x,ground=58,300,570
    d.rectangle((40,ground+1,1240,647),fill='#183b42')
    d.line((40,ground,1240,ground),fill='#8fc4ae',width=4)
    travel=(index*13+phase*13)*units
    for x in range(-2,24):
        sx=(x*67-travel)%1280
        d.line((sx,614,sx+24,614),fill='#2c5557',width=2)
    py=ground-bottom*units
    d.rounded_rectangle((player_x,py-height*units,player_x+units,py),6,fill=MINT)
    d.rectangle((player_x+38,py-height*units+17,player_x+45,py-height*units+25),fill=BG)
    obstacle=state['target_obstacle']
    sx=player_x+ox*units
    top=ground-(obstacle['bottom']+obstacle['height'])*units
    obottom=ground-obstacle['bottom']*units
    d.rounded_rectangle((sx,top,sx+obstacle['width']*units,obottom),4,fill=CORAL)
    text(d,57,195,obstacle['kind'].replace('_',' ').upper(),18,MUTED)
    text(d,56,229,f"Speed {state['current_speed']}",19,MUTED)
    if phase>.96 and not step['terminal']:
        text(d,1000,602,'CLEARED',20,MINT)


def wiki_canvas(d,trace,t,index,local,finished):
    step=trace['steps'][index]
    transition=local>.72 or finished
    current=step['next_state']['current_page'] if transition else step['request']['state']['current_page']
    if transition and not finished and index+1<len(trace['steps']):
        links=list(trace['steps'][index+1]['request']['questions']['action']['criteria'])
    elif finished:links=[]
    else:links=list(step['request']['questions']['action']['criteria'])
    d.rounded_rectangle((84,205,1196,570),15,fill='#f0f1e6')
    d.rectangle((84,205,1196,251),fill='#294751')
    text(d,112,216,'LOCAL ARTICLE GAME  /  '+current,19,INK)
    text(d,122,276,current,50,'#123343')
    text(d,122,345,'Follow one of these outgoing links:',21,'#536d6f')
    for j,link in enumerate(links):
        x,y=124+j*490,402
        selected=link==step['action'] and t>=INTRO and local>.48 and not transition
        d.rounded_rectangle((x,y,x+446,y+85),12,fill='#b4e7c8' if selected else '#e0e8df',outline='#517d75' if selected else '#c2d2c9',width=2)
        text(d,x+27,y+23,link,28,'#174e65')
        text(d,x+390,y+24,'→',27,'#174e65')
    if links and t>=INTRO and not transition:
        chosen=list(step['request']['questions']['action']['criteria']).index(step['action'])
        destination=(124+chosen*490+218,446)
        ratio=ease(min(1,local/.58))
        cx,cy=lerp(1100,destination[0],ratio),lerp(540,destination[1],ratio)
        d.polygon(((cx,cy),(cx+8,cy+27),(cx+15,cy+15),(cx+28,cy+10)),fill='#123745',outline='#ffffff')
    followed=index+(1 if transition else 0)
    path=trace['metrics']['path'][:followed+1]
    centered(d,611,' → '.join(path),27,MINT)


def frame(key,trace,spec,t):
    index,local,finished,_=moment(trace,spec,t)
    im=background(key).copy()
    d=ImageDraw.Draw(im)
    hud(d,key,trace,spec,t,index,local,finished)
    {'snake':snake_canvas,'platformer':platformer_canvas,'trex':trex_canvas,'wiki':wiki_canvas}[key](d,trace,t,index,local,finished)
    if finished:
        im=end_overlay(im,spec,bool(trace['metrics'].get('success')))
    return im


def timestamp(seconds):
    milliseconds=round(seconds*1000)
    return f'{milliseconds//3600000:02d}:{milliseconds//60000%60:02d}:{milliseconds//1000%60:02d}.{milliseconds%1000:03d}'


def subtitles(key,trace,spec,length):
    end=INTRO+len(trace['steps'])*spec['seconds_per_action']
    cues=[(0,INTRO,f"{spec['title']}. Goal: {spec['goal']} Qwen3.5-9B pilot, complete recorded episode.")]
    for i,step in enumerate(trace['steps']):
        start=INTRO+i*spec['seconds_per_action']
        cues.append((start,start+spec['seconds_per_action'],f"Decision {i+1}/{len(trace['steps'])}: {step['action'].replace('_',' ')}."))
    cues.append((end,length,spec['outcome']+'. '+spec['result']+'.'))
    return cues


def verify_video(video,expected):
    p=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,pix_fmt,width,height,r_frame_rate,nb_frames:format=duration','-of','json',str(video)],text=True))
    stream=p['streams'][0]
    if stream['codec_name']!='h264' or stream['pix_fmt']!='yuv420p' or (stream['width'],stream['height'])!=(W,H):
        raise ValueError('Unexpected video format')
    if abs(float(p['format']['duration'])-expected)>.1:
        raise ValueError('Unexpected gameplay duration')
    raw=video.read_bytes()
    if raw.index(b'moov')>raw.index(b'mdat'):raise ValueError('MP4 is not fast-start')
    return {'duration_seconds':float(p['format']['duration']),'frames':int(stream['nb_frames']),
            'width':W,'height':H,'fps':FPS,'codec':'h264','pixel_format':'yuv420p','faststart':True,
            'bytes':video.stat().st_size,'sha256':sha(video)}


def render(key,site,verify_only=False):
    spec=SPECS[key]
    source,trace=source_trace(key)
    replay=replay_episode(_game(trace['game'],ROOT/'examples/games/wiki-graph.json'),trace)
    length=duration(trace,spec)
    stem='gameplay-'+key
    media=site/'media'
    media.mkdir(parents=True,exist_ok=True)
    video=media/(stem+'.mp4')
    if not verify_only:
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-threads','2',str(video)]
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for i in range(round(length*FPS)):
                process.stdin.write(frame(key,trace,spec,i/FPS).tobytes())
            process.stdin.close()
            if process.wait()!=0:raise RuntimeError('ffmpeg failed')
        except BaseException:
            process.kill();process.wait();raise
        frame(key,trace,spec,INTRO+spec['seconds_per_action']*.4).save(media/(stem+'.jpg'),quality=90,optimize=True)
        cues=subtitles(key,trace,spec,length)
        (media/(stem+'.vtt')).write_text('WEBVTT\n\n'+'\n\n'.join(f'{timestamp(a)} --> {timestamp(b)}\n{caption}' for a,b,caption in cues)+'\n')
        transcript=f"{spec['title']} — complete recorded episode\n\nGoal: {spec['goal']}\n\n"
        transcript+='\n'.join(f'{timestamp(a)} {caption}' for a,_,caption in cues)
        transcript+=f"\n\nSource: {source.relative_to(ROOT)}\nSource SHA256: {sha(source)}\n"
        transcript+='This is the original local Python game, rendered from an exact re-execution of saved model actions. Smooth motion and playback timing are presentation only. The checkpoint is the original 100-step 9B pilot, not the later fully trained 9B model. No new model inference was performed. All logged actions are included; no successful episode was selected in place of a failure.\n'
        (media/(stem+'.txt')).write_text(transcript)
    info=verify_video(video,length)
    for ext in ('jpg','vtt','txt'):
        if not (media/(stem+'.'+ext)).exists():raise ValueError('Missing companion media file')
    return {'id':stem,'title':spec['title'],'goal':spec['goal'],'video':'media/'+stem+'.mp4',
            'poster':'media/'+stem+'.jpg','captions':'media/'+stem+'.vtt','transcript':'media/'+stem+'.txt',
            'source_path':str(source.relative_to(ROOT)),'source_sha256':sha(source),
            'model_label':'Qwen3.5-9B · 100-step pilot','checkpoint':trace['service_identity'],
            'seed':trace['seed'],'decision_count':len(trace['steps']),'episode_metrics':trace['metrics'],
            'engine_replay':replay,'all_logged_actions_included':True,'new_inference':False,
            'rendering':'Original local game canvas; verified state transitions with presentation-only tweening. Box runner positions use the local collision timing equations.',
            'outcome_title':spec['outcome'],'outcome_summary':spec['result'],**info}



def render_doom(capture_path, site, verify_only=False):
    capture_label=(capture_path/'capture.json').as_posix()
    capture_path=capture_path.resolve()
    capture_file=capture_path/'capture.json'
    capture=json.loads(capture_file.read_text())
    source=TRACE_DIR/'doom_basic-model-seed-10001.json'
    if (capture['status']!='passed' or not capture['all_saved_decisions_replayed']
            or capture['trace_sha256']!=sha(source) or capture['decision_count']!=11
            or not all(row['state_reward_terminal_match'] for row in capture['decision_boundaries'])
            or capture['terminal'] is not True or capture['kill_count']!=1):
        raise ValueError('Native Doom capture is not a complete verified successful replay')
    frames=[]
    for row in capture['frames']:
        path=(capture_path/row['file']).resolve()
        if not path.is_relative_to(capture_path) or sha(path)!=row['sha256']:
            raise ValueError('Native Doom frame path/hash mismatch')
        with Image.open(path) as image:
            if image.size!=(320,240):raise ValueError('Unexpected native Doom frame size')
            frames.append(image.convert('RGB').resize((832,624),Image.Resampling.NEAREST))
    # Original engine runs at 35 tics/second; 7 displayed tics/sec is 0.2x speed.
    intro,outro,capture_fps=2.0,3.0,7
    play_seconds=len(frames)/capture_fps
    length=math.ceil((intro+play_seconds+outro)*FPS)/FPS
    used={min(len(frames)-1,max(0,int((i/FPS-intro)*capture_fps))) for i in range(round(length*FPS))}
    if used!=set(range(len(frames))):raise ValueError('A native screen frame would be skipped')
    spec={'outcome':'TARGET ELIMINATED','result':'Goal reached · 1 / 1 target · engine reward 54'}
    def draw_frame(t):
        index=min(len(frames)-1,max(0,int((t-intro)*capture_fps)))
        im=Image.new('RGB',(W,H),BG)
        im.paste(frames[index],(224,88))
        d=ImageDraw.Draw(im)
        text(d,38,18,'DOOM',31,MINT)
        text(d,235,25,'GOAL  Eliminate the target.',24,INK)
        text(d,1040,27,'9B pilot',21,MUTED)
        text(d,35,125,'NATIVE SCREEN',16,MINT)
        text(d,35,163,'0.2× playback',18,INK)
        decision=capture['frames'][index]['decision']
        text(d,35,207,f'Decision {decision} / 11',18,MUTED)
        if decision:
            action=capture['decision_boundaries'][decision-1]['action'].split('_')
            text(d,1080,158,'ACTION',15,MUTED)
            for j,word in enumerate(action):text(d,1080,193+j*32,word.upper(),20,INK)
        text(d,35,580,'Seed 10001',16,MUTED)
        text(d,35,609,'All frames kept',16,MUTED)
        text(d,35,638,'CPU replay',16,MUTED)
        if t>=intro+play_seconds:
            im=end_overlay(im,spec,True)
            d=ImageDraw.Draw(im)
            centered(d,473,'Last available screen held; terminal engine state has no screen buffer.',17,MUTED)
        return im
    media=site/'media'
    video=media/'gameplay-doom.mp4'
    if not verify_only:
        command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24',
                 '-video_size',f'{W}x{H}','-framerate',str(FPS),'-i','-','-an','-c:v','libx264',
                 '-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-threads','2',str(video)]
        process=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            for i in range(round(length*FPS)):process.stdin.write(draw_frame(i/FPS).tobytes())
            process.stdin.close()
            if process.wait()!=0:raise RuntimeError('Doom ffmpeg failed')
        except BaseException:
            process.kill();process.wait();raise
        draw_frame(intro+2).save(media/'gameplay-doom.jpg',quality=90,optimize=True)
        cues=[(0,intro,'Doom. Goal: eliminate the visible target. Original 9B pilot checkpoint.'),
              (intro,intro+play_seconds,'The complete native game-screen sequence. All 11 recorded actions are replayed; playback is slowed to 0.2x.'),
              (intro+play_seconds,length,'Target eliminated: 1 of 1. Goal reached; engine reward 54. The last available screen is held because the terminal engine state has no screen buffer.')]
        (media/'gameplay-doom.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{timestamp(a)} --> {timestamp(b)}\n{caption}' for a,b,caption in cues)+'\n')
        (media/'gameplay-doom.txt').write_text('DOOM — complete native gameplay replay\n\n'+'\n\n'.join(caption for _,_,caption in cues)
            +f"\n\nSource: {source.relative_to(ROOT)}\nSource SHA256: {sha(source)}\nCapture SHA256: {sha(capture_file)}\n"
            +'Every captured native screen frame is included, with nearest-neighbor scaling and no synthesized game imagery. CPU-only replay; no new model inference. All saved action/state/reward/terminal checks matched. The checkpoint is the original 100-step pilot, not the later completed full-pass checkpoint.\n')
    info=verify_video(video,length)
    return {'id':'gameplay-doom','title':'DOOM','goal':capture['goal'],'video':'media/gameplay-doom.mp4',
            'poster':'media/gameplay-doom.jpg','captions':'media/gameplay-doom.vtt','transcript':'media/gameplay-doom.txt',
            'source_path':str(source.relative_to(ROOT)),'source_sha256':sha(source),
            'capture_path':capture_label,'capture_sha256':sha(capture_file),
            'capture':capture,'model_label':'Qwen3.5-9B · 100-step pilot','checkpoint':capture['model_identity'],
            'seed':capture['seed'],'decision_count':capture['decision_count'],
            'episode_metrics':{'terminal':True,'kill_count':1,'engine_total_reward':capture['total_reward'],'success':True},
            'engine_replay':{'matched':True,'game':'doom_basic','steps':11},
            'native_screen_frames':len(frames),'all_native_frames_included':True,'native_frame_indices_rendered':sorted(used),'native_playback_rate':.2,
            'all_logged_actions_included':True,'new_inference':False,'gpu_used':False,
            'rendering':'Native ViZDoom game.get_state().screen_buffer frames, 4:3 aspect preserved. Last available frame held after the terminal state; no post-kill image synthesized.',
            'outcome_title':spec['outcome'],'outcome_summary':spec['result'],**info}


def gameplay_overview(items,site,verify_only=False):
    source_episode_count=len(items)
    items=[item for item in items if item.get('episode_metrics',{}).get('success') is True]
    if not items:
        raise ValueError('No explicitly successful episode is available for the demo overview')
    order={'gameplay-doom':0,'gameplay-trex':1,'gameplay-wiki':2}
    items=sorted(items,key=lambda item:order.get(item['id'],len(order)))
    selection=('Successful full episodes selected from saved fixed-seed 10001 9B-pilot evidence. '
               'Only successfully completed episodes are included. This curated demo does not estimate a success rate.')
    for item in items:
        if sha(site/item['video'])!=item['sha256']:
            raise ValueError(f"Source episode video hash differs: {item['id']}")
        if item.get('all_logged_actions_included') is not True or item.get('new_inference') is not False:
            raise ValueError(f"Episode does not declare a complete saved-action replay: {item['id']}")
    video=site/'media/gameplay-overview.mp4'
    expected=sum(item['duration_seconds'] for item in items)
    chapters=[]
    offset=0.0
    cues=[]
    for item in items:
        end=offset+item['duration_seconds']
        chapters.append({'id':item['id'],'title':item['title'],'start_seconds':offset,
                         'end_seconds':end,'complete_episode':True,'success':True,
                         'source_video':item['video'],'source_frames':item['frames'],
                         'source_video_sha256':item['sha256']})
        intro_seconds=2 if item['id']=='gameplay-doom' else 3
        cues.append((offset,min(end,offset+intro_seconds),item['title']+'. Goal: '+item['goal']))
        outro_seconds=3 if item['id']=='gameplay-doom' else 5
        cues.append((max(offset+3,end-outro_seconds),end,item['outcome_title']+'. '+item['outcome_summary']+'.'))
        offset=end
    if not verify_only:
        with tempfile.TemporaryDirectory(prefix='open-jev-full-gameplay-') as temp:
            concat=Path(temp)/'concat.txt'
            concat.write_text(''.join("file '"+str((site/item['video']).resolve()).replace("'","'\\''")+"'\n" for item in items))
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),
                            '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',
                            '-r',str(FPS),'-g',str(FPS*2),'-an','-movflags','+faststart',str(video)],check=True)
        Image.open(site/items[0]['poster']).save(site/'media/gameplay-overview.jpg',quality=90,optimize=True)
        (site/'media/gameplay-overview.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{timestamp(a)} --> {timestamp(b)}\n{caption}' for a,b,caption in cues)+'\n')
        (site/'media/gameplay-overview.txt').write_text('SUCCESSFUL COMPLETE GAMEPLAY EPISODES\n\n'
            +selection+'\n\n'
            'Every chapter includes an entire selected saved 9B-pilot episode from its initial state through its recorded successful outcome. No steps or captured game frames are omitted within an episode. Doom uses native game-screen frames; the original local Python games use a dedicated gameplay canvas. No new model inference.\n\n'
            +'\n'.join(f"{timestamp(chapter['start_seconds'])} {chapter['title']} — full episode" for chapter in chapters)+'\n')
    info=verify_video(video,expected)
    if info['frames']!=sum(item['frames'] for item in items):
        raise ValueError('Overview frame count differs from the complete source episodes')
    return {'id':'gameplay-overview','video':'media/gameplay-overview.mp4','poster':'media/gameplay-overview.jpg',
            'captions':'media/gameplay-overview.vtt','transcript':'media/gameplay-overview.txt',
            'complete_episode_count':len(items),'source_episode_count':source_episode_count,
            'selection':selection,'success_only':True,'chapters':chapters,**info}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',type=Path,default=ROOT/'site')
    parser.add_argument('--games',nargs='+',choices=list(SPECS),default=list(SPECS))
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--doom-capture',type=Path,help='Directory containing native Doom capture.json and frames/')
    args=parser.parse_args()
    if args.verify_only:
        items=[render(key,args.site,True) for key in args.games]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            tasks=[pool.submit(render,key,args.site) for key in args.games]
            items=[task.result() for task in tasks]
    if args.doom_capture:
        doom=render_doom(args.doom_capture,args.site,args.verify_only)
        insert=1 if items and items[0]['id']=='gameplay-snake' else 0
        items.insert(insert,doom)
    overview=gameplay_overview(items,args.site,args.verify_only)
    result={'schema_version':1,'renderer':'scripts/render_gameplay_videos.py','renderer_sha256':sha(__file__),
            'engine_sha256':sha(ROOT/'jev/games.py'),'selection':'Per-episode evidence retains fixed-seed 10001 saved 9B-pilot episodes. The overview includes only explicitly successful complete episodes; it is a curated demo, not a success-rate estimate.',
            'all_engine_replays_matched':all(item['engine_replay']['matched'] for item in items),
            'count':len(items),'total_video_bytes':sum(item['bytes'] for item in items),'items':items,'overview':overview}
    (args.site/'media/gameplay-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
