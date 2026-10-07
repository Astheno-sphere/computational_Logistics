#!/usr/bin/env python3
"""Render auditable demo clips from site/catalog.json, without calling a model.

Requires Python 3.10+, Pillow and ffmpeg/ffprobe on PATH. On macOS the renderer
uses system fonts; on Linux install fonts-dejavu-core. No GPU is used.

    python scripts/render_demo_videos.py --workers 3
    python scripts/render_demo_videos.py --verify-only

Every animation uses the catalog's source data. Saved trajectories are retimed
and redrawn as state diagrams, never represented as original screen recordings.
Contract walkthroughs deliberately have no synthetic model answers. MP4 files
are silent; English VTT captions and plain text transcripts carry the narration.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS, DURATION = 1280, 720, 12, 16
BG = '#081a23'
PANEL = '#102833'
EDGE = '#24434b'
INK = '#f2f0e7'
MUTED = '#a5bdc1'
MINT = '#adf6cd'
GOLD = '#f5cd8c'
CORAL = '#f19686'


def font_file() -> str:
    choices = ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
               '/System/Library/Fonts/Helvetica.ttc',
               '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
               '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
    for path in choices:
        if Path(path).is_file():
            return path
    raise RuntimeError('Install a TrueType sans-serif font (e.g. fonts-dejavu-core).')


@lru_cache(maxsize=40)
def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_file(), size=size)


def compact(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(', ', ': '))


def clip(text: Any, width: float, size: int) -> str:
    text = re.sub(r'\s+', ' ', compact(text)).strip()
    if font(size).getlength(text) <= width:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if font(size).getlength(text[:middle] + '…') <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + '…'


def wrap(text: Any, width: float, size: int, max_lines: int = 100) -> list[str]:
    result: list[str] = []
    for paragraph in compact(text).splitlines():
        words = paragraph.split()
        if not words:
            result.append('')
            continue
        line = ''
        for word in words:
            candidate = f'{line} {word}'.strip()
            if line and font(size).getlength(candidate) > width:
                result.append(line)
                line = word
            else:
                line = candidate
        result.append(line)
    if len(result) > max_lines:
        result = result[:max_lines]
        result[-1] = clip(result[-1] + ' …', width, size)
    return [clip(line, width, size) for line in result]


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: Any,
         size: int = 20, color: str = INK) -> None:
    draw.text(xy, compact(value), font=font(size), fill=color)


def paragraph(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: Any,
              width: int, size: int = 20, max_lines: int = 6,
              color: str = INK, line_height: int | None = None) -> int:
    x, y = xy
    height = line_height or round(size * 1.4)
    for line in wrap(value, width, size, max_lines):
        text(draw, (x, y), line, size, color)
        y += height
    return y


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str,
         color: str = MINT, size: int = 14) -> int:
    x, y = xy
    width = int(font(size).getlength(label)) + 22
    draw.rounded_rectangle((x, y, x + width, y + 27), 13, fill=EDGE)
    text(draw, (x + 11, y + 5), label, size, color)
    return width


def questions(item: dict) -> dict:
    value = item.get('request') or {}
    if not isinstance(value, dict):
        return {}
    if 'questions' in value:
        return value['questions']
    if 'question' in value:
        saved = item.get('answer') or {}
        key = saved.get('question_id', 'decision')
        return {key: {'type': value.get('kind', 'choice'),
                      'instructions': value['question'],
                      'criteria': value.get('options', [])}}
    return {}


def answer_map(item: dict) -> dict:
    value = item.get('answer') or {}
    if not isinstance(value, dict):
        return {}
    if item.get('answer_format') == 'saved_prediction_record':
        request = item['request']
        options = request.get('options', [])
        probabilities = value.get('probabilities', [])
        if len(options) != len(probabilities) or not probabilities:
            raise ValueError(f"Invalid saved prediction vector in {item['id']}")
        kind = request.get('kind', value.get('kind', 'choice'))
        decoded = {'type': kind, 'probabilities': dict(zip(options, probabilities))}
        if kind == 'noul':
            if options != ['no', 'yes']:
                raise ValueError('Binary answer option order is not no/yes')
            decoded['noul'] = probabilities[1]
        elif kind == 'score':
            decoded['score'] = sum(i * probability for i, probability in enumerate(probabilities))
        else:
            decoded['choice'] = options[max(range(len(probabilities)), key=probabilities.__getitem__)]
        return {value.get('question_id', 'decision'): decoded}
    if 'answers' in value:
        return value['answers']
    if 'response' in value:
        return value['response'].get('answers', {})
    if 'type' in value:
        return {next(iter(questions(item)), 'action'): value}
    return value


def state_of(item: dict) -> Any:
    request = item.get('request') or {}
    return request.get('state', request) if isinstance(request, dict) else request


def context_lines(item: dict) -> str:
    state = state_of(item)
    display = item.get('display_context')
    if display:
        try:
            parsed = json.loads(display) if isinstance(display, str) else display
            state = parsed
        except (ValueError, TypeError):
            if not isinstance(display, str) or not display.lstrip().startswith(('{', '[')):
                return compact(display)
    if not isinstance(state, dict):
        return compact(state)
    if isinstance(state.get('text'), str):
        # Preserve document lines instead of displaying JSON string escapes.
        role = state.get('requested_role')
        return (f'Requested field: {role}\n\n' if role else '') + state['text']
    parts = []
    for key, value in state.items():
        if key in ('coordinates', 'physics', 'timing_policy', 'policy'):
            continue
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                parts.append(f'{key}.{nested_key}: {compact(nested_value)}')
        else:
            parts.append(f'{key}: {compact(value)}')
    return '\n'.join(parts)


def trajectory_frame(item: dict, seconds: float) -> tuple[dict | None, int]:
    frames = item.get('frames') or []
    if not frames:
        return None, 0
    # Fixed initial state, every logged action in order, then fixed final state.
    progress = min(1.0, max(0.0, (seconds - 3.0) / 9.0))
    index = min(len(frames) - 1, int(progress * len(frames)))
    return frames[index], index


def frame_state(item: dict, seconds: float) -> Any:
    frame, _ = trajectory_frame(item, seconds)
    if frame:
        if seconds >= 12:
            next_state = frame.get('next_state')
            return next_state if next_state is not None else frame.get('state', frame.get('request', {}).get('state', state_of(item)))
        return frame.get('state', frame.get('request', {}).get('state', state_of(item)))
    return state_of(item)


def game_visual(draw: ImageDraw.ImageDraw, item: dict, seconds: float) -> bool:
    kind = item.get('visual_kind', '')
    state = frame_state(item, seconds)
    if not isinstance(state, dict):
        return False
    frame, index = trajectory_frame(item, seconds)
    frames = item.get('frames') or []
    # Only diagrams derived from observed states, no simulated successful moves.
    if kind == 'painting' and item.get('pixel_predictions'):
        pixels = item['pixel_predictions']
        width, height = int(state.get('width', 8)), int(state.get('height', 8))
        cell = min(272 // width, 272 // height)
        x0, y0 = 77, 282
        visible = min(len(pixels), max(0, int((seconds - 2.5) / 9.5 * len(pixels))))
        for y in range(height):
            for x in range(width):
                draw.rectangle((x0+x*cell, y0+y*cell, x0+(x+1)*cell-2, y0+(y+1)*cell-2), fill=EDGE)
        for pixel in pixels[:visible]:
            if 'rgb' in pixel:
                color = tuple(round(channel) for channel in pixel['rgb'])
            else:
                values, options = pixel['probabilities'], pixel['options']
                if len(values) != len(options):
                    raise ValueError('Painting probability and option dimensions disagree')
                winner = str(options[max(range(len(values)), key=values.__getitem__)])
                match = re.search(r'RGB\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]', winner)
                if not match:
                    raise ValueError(f'No RGB color in recorded painting option: {winner}')
                color = tuple(int(channel) for channel in match.groups())
            if len(color) != 3 or any(channel < 0 or channel > 255 for channel in color):
                raise ValueError('Invalid RGB channels in saved prediction')
            x, y = pixel['x'], pixel['y']
            draw.rectangle((x0+x*cell, y0+y*cell, x0+(x+1)*cell-2, y0+(y+1)*cell-2), fill=color)
        text(draw, (78, 247), f'SAVED PIXEL PREDICTIONS · {visible} / {len(pixels)}', 14, MUTED)
        text(draw, (378, 288), 'PROMPT', 14, MUTED)
        paragraph(draw, (378, 321), state.get('image_description', ''), 264, 20, 8)
        text(draw, (378, 547), 'No reference pixels shown.', 16, MUTED)
        return True
    if kind == 'snake' and state.get('snake_head_first'):
        width, height = state.get('width', 6), state.get('height', 6)
        cell = min(260 // width, 260 // height)
        x0, y0 = 78, 281
        for y in range(height):
            for x in range(width):
                draw.rounded_rectangle((x0+x*cell, y0+y*cell,
                                        x0+(x+1)*cell-3, y0+(y+1)*cell-3), 4, fill=EDGE)
        food = state.get('food')
        if food and 0 <= food[0] < width and 0 <= food[1] < height:
            fx, fy = x0+food[0]*cell, y0+food[1]*cell
            draw.ellipse((fx+9, fy+9, fx+cell-12, fy+cell-12), fill=CORAL)
        for i, (x, y) in enumerate(state['snake_head_first']):
            if not (0 <= x < width and 0 <= y < height):
                continue
            draw.rounded_rectangle((x0+x*cell+2, y0+y*cell+2,
                                    x0+(x+1)*cell-5, y0+(y+1)*cell-5), 7,
                                   fill=MINT if i == 0 else '#639c8a')
        text(draw, (376, 305), f'{width} × {height} board', 25)
        text(draw, (376, 347), 'Head ' + compact(state['snake_head_first'][0]), 20, MINT)
        text(draw, (376, 382), 'Food ' + compact(food), 20, CORAL)
        text(draw, (376, 417), 'Direction: ' + str(state.get('direction', '')), 19, MUTED)
        if seconds >= 12 and item.get('episode_metrics', {}).get('collision'):
            pill(draw, (376, 470), 'COLLISION · EPISODE ENDED', CORAL, 13)
    elif kind in ('platformer', 'tile_platformer') and 'terrain' in state:
        columns = state['terrain'].get('columns', [])
        if not columns:
            return False
        x0, y0, cell = 70, 508, 12
        for x, height in enumerate(columns[:48]):
            if height is not None:
                draw.rectangle((x0+x*cell, y0-height*25, x0+(x+1)*cell-2, y0+23), fill=EDGE)
                draw.rectangle((x0+x*cell, y0-height*25, x0+(x+1)*cell-2, y0-height*25+3), fill='#77ad9c')
        player = state.get('player', {})
        px, py = x0+player.get('x', 0)*cell, y0-player.get('y', 0)*25-19
        draw.rounded_rectangle((px, py, px+13, py+18), 3, fill=MINT)
        flag_x = x0 + state['terrain'].get('flag_x', len(columns)-1)*cell
        draw.line((flag_x, 453, flag_x, 508), fill=GOLD, width=2)
        draw.polygon(((flag_x, 453), (flag_x+17, 461), (flag_x, 470)), fill=GOLD)
        text(draw, (76, 296), 'Original tile simulator', 26)
        text(draw, (76, 341), f"Player x={player.get('x')} · y={player.get('y')}", 21, MINT)
        text(draw, (76, 375), f"Motion: {player.get('jump_phase', 'unknown')}", 20, MUTED)
    elif kind in ('trex', 'trex_runner') and 'target_obstacle' in state:
        obstacle = state['target_obstacle']
        draw.line((82, 511, 640, 511), fill=EDGE, width=3)
        draw.rounded_rectangle((134, 425, 172, 510), 5, fill=MINT)
        bottom = float(obstacle.get('bottom', 0))
        height = float(obstacle.get('height', 1))
        width = float(obstacle.get('width', 1))
        draw.rounded_rectangle((472, 510-(bottom+height)*40,
                                472+width*40, 510-bottom*40), 3, fill=CORAL)
        text(draw, (82, 298), str(obstacle.get('kind', 'obstacle')).replace('_', ' '), 28)
        text(draw, (82, 340), f"Speed {state.get('current_speed')} · height {height:g} · bottom {bottom:g}", 20, MUTED)
        text(draw, (82, 540), 'Observed geometry, one decision per obstacle', 17, MUTED)
    elif kind == 'doom' and 'nearest_visible_enemy' in state:
        enemy = state.get('nearest_visible_enemy') or {}
        cx, cy, radius = 254, 416, 108
        for rad in (36, 72, 108):
            draw.ellipse((cx-rad, cy-rad, cx+rad, cy+rad), outline=EDGE, width=2)
        draw.line((cx-radius, cy, cx+radius, cy), fill=EDGE)
        draw.line((cx, cy-radius, cx, cy+radius), fill=EDGE)
        bearing = float(enemy.get('relative_bearing_deg', 0))
        theta = math.radians(bearing - 90)
        target_x, target_y = cx + 88*math.cos(theta), cy + 88*math.sin(theta)
        draw.line((cx, cy, target_x, target_y), fill=CORAL, width=3)
        draw.ellipse((target_x-7, target_y-7, target_x+7, target_y+7), fill=CORAL)
        draw.polygon(((cx, cy-10), (cx-7, cy+9), (cx+7, cy+9)), fill=MINT)
        text(draw, (397, 322), 'Telemetry replay', 23)
        text(draw, (397, 369), f"Health {state.get('health', 0):g}", 21, MINT)
        text(draw, (397, 405), f"Ammo {state.get('ammo', 0):g}", 21, MINT)
        text(draw, (397, 441), f'Bearing {bearing:.1f}°', 20, CORAL)
        text(draw, (94, 540), 'Reconstructed state; not first-person footage', 17, MUTED)
    elif kind == 'wiki' and 'current_page' in state:
        text(draw, (78, 298), 'CURRENT ARTICLE', 14, MUTED)
        paragraph(draw, (78, 326), state['current_page'], 550, 35, 2, MINT)
        text(draw, (78, 412), 'TARGET ARTICLE', 14, MUTED)
        paragraph(draw, (78, 440), state.get('target_page', ''), 550, 30, 2)
        text(draw, (78, 519), 'Follow only an offered outgoing link.', 20, MUTED)
    elif kind == 'tictactoe' and ('board' in state):
        board = state['board']
        if isinstance(board, list) and len(board) == 3 and isinstance(board[0], (list, str)):
            board = [v for row in board for v in row]
        if not isinstance(board, (list, str)) or len(board) != 9:
            return False
        for index, mark in enumerate(board):
            x, y = 104+(index%3)*83, 282+(index//3)*83
            draw.rounded_rectangle((x,y,x+75,y+75), 9, fill=EDGE)
            if str(mark) not in ('', ' ', '.', 'None', 'null'):
                text(draw, (x+23, y+16), str(mark), 40, MINT)
        paragraph(draw, (396, 319), 'Choose a legal move from this board state.', 230, 25, 5)
    else:
        return False
    if frames:
        label = f'LOGGED STEP {index + 1:02d} / {len(frames):02d}'
        if seconds >= 12:
            label = (f'FINAL LOGGED STATE · {len(frames)} STEPS' if frame.get('next_state') is not None
                     else f'LAST OBSERVED STATE · TERMINAL AT {len(frames)} STEPS')
        text(draw, (78, 247), label, 14, MUTED)
    else:
        text(draw, (78, 247), 'OBSERVED STATE · ONE DECISION', 14, MUTED)
    return True


def input_visual(draw: ImageDraw.ImageDraw, item: dict, seconds: float) -> None:
    if game_visual(draw, item, seconds):
        return
    value = context_lines(item)
    state = state_of(item)
    if item.get('visual_kind') == 'browser' and isinstance(state, dict) and 'snapshot' in state:
        snapshot = state['snapshot']
        draw.rounded_rectangle((74, 277, 646, 540), 11, fill=BG, outline=EDGE)
        text(draw, (94, 291), clip(snapshot.get('url', 'DOM snapshot'), 528, 17), 17, MUTED)
        draw.line((74, 325, 646, 325), fill=EDGE)
        goal = str(state.get('goal', snapshot.get('visible_text', ''))).split('\n\n')[0]
        paragraph(draw, (94, 341), goal, 525, 21, 2)
        y = 408
        for element in snapshot.get('elements', [])[:3]:
            draw.rounded_rectangle((95, y, 625, y+36), 5, outline=EDGE)
            text(draw, (107, y+8), clip(f"{element.get('label')}  [{element.get('id')}]", 507, 18), 18, MUTED)
            y += 40
        text(draw, (77, 247), 'DOM SNAPSHOT · PROPOSAL ONLY', 14, MUTED)
        return
    text(draw, (78, 247), 'SUPPLIED CONTEXT / EXCERPT', 14, MUTED)
    paragraph(draw, (78, 284), value, 562, 21, 9, INK, 29)
    if len(wrap(value, 562, 21)) > 9:
        text(draw, (78, 551), 'Full request is linked with the source record.', 16, MUTED)


def answer_label(answer: dict) -> str:
    if not isinstance(answer, dict):
        return compact(answer)
    if 'choice' in answer:
        return compact(answer['choice'])
    if 'noul' in answer:
        return f"P(yes) = {float(answer['noul']):.3f}"
    if 'score' in answer:
        return f"Score = {float(answer['score']):.3f}"
    return compact(answer)


def question_panel(draw: ImageDraw.ImageDraw, item: dict, seconds: float) -> None:
    qs, answers = questions(item), answer_map(item)
    frame, _ = trajectory_frame(item, seconds)
    if frame:
        qs = frame.get('request', {}).get('questions', qs)
        raw_answer = frame.get('answer')
        if raw_answer:
            answers = {next(iter(qs), 'action'): raw_answer}
    replay = item['evidence_kind'] == 'model_replay'
    stage = 0 if seconds < 3.5 else 1 if seconds < 7 else 2
    title = ('ONE STRUCTURED REQUEST', 'PARALLEL TYPED QUESTIONS',
             'RECORDED MODEL OUTPUT' if replay else 'INTERFACE CONTRACT')[stage]
    if item.get('pixel_predictions'):
        title = ('RECORDED PIXEL DECISIONS', 'REPRESENTATIVE PIXEL QUESTION', 'ONE PIXEL / RECORDED OUTPUT')[stage]
    text(draw, (742, 247), title, 14, MINT if replay else GOLD)
    entries = list(qs.items())
    if not entries:
        paragraph(draw, (742, 296), item.get('description', ''), 443, 24, 6)
        return
    if stage == 0:
        count = len(item['records']) if item.get('pixel_predictions') else len(qs)
        text(draw, (742, 293), str(count), 76, MINT)
        text(draw, (742, 382), 'typed question' + ('s' if count != 1 else ''), 28)
        types = ' · '.join(dict.fromkeys(q.get('type', 'decision') for q in qs.values()))
        text(draw, (742, 429), clip(types, 442, 22), 22, MUTED)
        explanation = ('The canvas is reconstructed from the recorded probability distribution for each pixel.'
                       if item.get('pixel_predictions') else 'State and questions go in one request. Each answer keeps its declared type.')
        paragraph(draw, (742, 479), explanation, 436, 21, 3, MUTED)
        return
    if len(entries) == 1 and replay and stage == 2:
        key, question = entries[0]
        answer = answers.get(key, {})
        text(draw, (742, 290), clip(key, 443, 21), 21, MUTED)
        paragraph(draw, (742, 327), answer_label(answer), 443, 34, 2, MINT)
        probabilities = answer.get('probabilities', {}) if isinstance(answer, dict) else {}
        y = 417
        for option, probability in sorted(probabilities.items(), key=lambda v: -v[1])[:3]:
            text(draw, (742, y), clip(option, 330, 18), 18, MUTED)
            text(draw, (1113, y), f'{probability:.3f}', 18, INK)
            draw.rounded_rectangle((742, y+26, 1193, y+31), 2, fill=EDGE)
            if probability > 0:
                draw.rounded_rectangle((742, y+26, 742+max(3,451*probability), y+31), 2, fill=MINT)
            y += 47
        return
    # Cycle batches in larger contracts; never hide the existence of omitted heads.
    batches = max(1, math.ceil(len(entries)/5))
    batch = min(batches-1, int(max(0, seconds-7) / max(1,9/batches))) if stage == 2 else 0
    visible = entries[batch*5:batch*5+5]
    y = 291
    for key, question in visible:
        draw.line((742, y+48, 1196, y+48), fill=EDGE)
        text(draw, (742, y), clip(key.replace('_', ' '), 271, 19), 19)
        kind = str(question.get('type', 'decision'))
        if stage == 2 and replay and key in answers:
            value = answer_label(answers[key])
            text(draw, (742, y+23), clip(value, 436, 18), 18, MINT)
        else:
            criteria = question.get('criteria', {})
            details = ' · '.join(str(v) for v in criteria) if isinstance(criteria, (dict,list)) else ''
            text(draw, (742, y+23), clip(details or question.get('instructions', ''), 436, 16), 16, MUTED)
        pill(draw, (1096, y-2), kind, MINT if replay else GOLD, 12)
        y += 54
    if batches > 1:
        text(draw, (742, 568), f'Showing {batch*5+1}–{batch*5+len(visible)} of {len(entries)} questions', 14, MUTED)
    if not replay and stage == 2:
        draw.rounded_rectangle((735, 524, 1204, 577), 8, fill='#3d3226')
        text(draw, (750, 534), 'No model response recorded', 19, GOLD)
        text(draw, (750, 558), 'Request contract only; evaluation pending.', 14, GOLD)


def make_frame(item: dict, seconds: float) -> Image.Image:
    im = Image.new('RGB', (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(im)
    replay = item['evidence_kind'] == 'model_replay'
    text(draw, (42, 28), 'OPEN-JEV', 20, MINT)
    text(draw, (189, 31), '/  DECISIONS IN MOTION', 14, MUTED)
    badge = 'SAVED MODEL REPLAY' if replay else 'INTERFACE WALKTHROUGH'
    label_width = int(font(13).getlength(badge)) + 22
    pill(draw, (1238-label_width, 24), badge, MINT if replay else GOLD, 13)
    text(draw, (41, 81), clip(item['title'], 1193, 43), 43)
    text(draw, (43, 137), clip(item.get('description', ''), 1189, 20), 20, MUTED)
    stage = 0 if seconds < 3.5 else 1 if seconds < 7 else 2
    for i, title in enumerate(('INPUT', 'TYPED QUESTIONS', 'RECORDED RESULT' if replay else 'CONTRACT ONLY')):
        x = 44+i*397
        color = MINT if i <= stage and replay else GOLD if i <= stage else EDGE
        draw.ellipse((x, 181, x+20, 201), fill=color)
        text(draw, (x+6, 184), str(i+1), 12, BG if i <= stage else MUTED)
        text(draw, (x+31, 183), title, 14, INK if i == stage else MUTED)
        if i < 2:
            draw.line((x+208, 191, x+365, 191), fill=EDGE, width=2)
    draw.rounded_rectangle((42, 228, 690, 588), 16, fill=PANEL, outline=EDGE)
    draw.rounded_rectangle((715, 228, 1238, 588), 16, fill=PANEL, outline=EDGE)
    input_visual(draw, item, seconds)
    question_panel(draw, item, seconds)
    status = item.get('result_summary', '') if seconds >= 7 else item.get('evidence_label', '')
    paragraph(draw, (44, 605), status, 1190, 18, 2, MINT if replay else GOLD, 23)
    limits = item.get('limitations', '')
    if isinstance(limits, list):
        limits = ' '.join(limits)
    text(draw, (44, 657), clip(limits, 1186, 14), 14, MUTED)
    source = item.get('source_path', '')
    source_short = str(source).split('/')[-1]
    model = item.get('model_label', '')
    footer = f"{model}  •  {source_short}  •  Retimed visualization" if replay else f"{source_short}  •  No inference performed"
    text(draw, (44, 688), clip(footer, 1155, 13), 13, MUTED)
    draw.rectangle((0, 716, int(WIDTH*seconds/DURATION), 719), fill=MINT if replay else GOLD)
    return im


def timestamp(seconds: float) -> str:
    return f'00:{int(seconds)//60:02d}:{int(seconds)%60:02d}.{int(seconds%1*1000):03d}'


def narration(item: dict) -> list[tuple[float, float, str]]:
    limits = item.get('limitations', '')
    if isinstance(limits, list):
        limits = ' '.join(limits)
    count = len(item['records']) if item.get('pixel_predictions') else len(questions(item))
    evidence = 'Saved model response replay.' if item['evidence_kind'] == 'model_replay' else 'Interface walkthrough. No model inference was performed.'
    count_sentence = (f'The canvas combines {count} saved typed decisions.' if item.get('pixel_predictions')
                      else f"The request contains {count} typed question{'s' if count != 1 else ''}.")
    return [
        (0, 3.5, f"{item['title']}. {evidence}"),
        (3.5, 7, f"{item.get('description', '')} {count_sentence}"),
        (7, 12, item.get('result_summary', '') or item.get('evidence_label', '')),
        (12, DURATION, str(limits)),
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_one(task: tuple[dict, str]) -> dict:
    item, site_string = task
    site = Path(site_string)
    for field in ('video', 'poster', 'captions'):
        path = (site/item[field]).resolve()
        if not path.is_relative_to(site.resolve()):
            raise ValueError(f'Output path escapes site root: {item[field]}')
        path.parent.mkdir(parents=True, exist_ok=True)
    video, poster, captions = (site/item[key] for key in ('video', 'poster', 'captions'))
    if item['evidence_kind'] == 'interface_walkthrough' and item.get('answer'):
        raise ValueError(f"Contract walkthrough {item['id']} has an answer; resolve evidence before rendering.")
    if item['evidence_kind'] == 'model_replay' and not item.get('answer'):
        raise ValueError(f"Model replay {item['id']} has no saved answer.")
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
               '-pixel_format', 'rgb24', '-video_size', f'{WIDTH}x{HEIGHT}',
               '-framerate', str(FPS), '-i', '-', '-an', '-c:v', 'libx264',
               '-preset', 'fast', '-crf', '24', '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', '-threads', '2', str(video)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        frame_cache = {}
        for frame in range(FPS*DURATION):
            seconds = frame/FPS
            stage = 0 if seconds < 3.5 else 1 if seconds < 7 else 2
            _, trajectory_index = trajectory_frame(item, seconds)
            batches = max(1, math.ceil(len(questions(item))/5))
            batch = min(batches-1, int(max(0, seconds-7) / max(1,9/batches))) if stage == 2 else 0
            pixel_count = len(item.get('pixel_predictions') or [])
            visible_pixels = min(pixel_count, max(0, int((seconds-2.5)/9.5*pixel_count)))
            key = (stage, trajectory_index, seconds >= 12, batch, visible_pixels)
            if key not in frame_cache:
                frame_cache[key] = make_frame(item, seconds)
            image = frame_cache[key].copy()
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 716, WIDTH, HEIGHT), fill=BG)
            draw.rectangle((0, 716, int(WIDTH*seconds/DURATION), HEIGHT),
                           fill=MINT if item['evidence_kind'] == 'model_replay' else GOLD)
            proc.stdin.write(image.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f'ffmpeg failed for {item["id"]}')
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    poster_seconds = 13 if item.get('frames') or item.get('pixel_predictions') else 8.5
    make_frame(item, poster_seconds).save(poster, quality=88, optimize=True)
    cues = narration(item)
    captions.write_text('WEBVTT\n\n' + '\n\n'.join(
        f'{timestamp(start)} --> {timestamp(end)}\n{value}'
        for start, end, value in cues if value) + '\n', encoding='utf-8')
    transcript = captions.with_suffix('.txt')
    transcript.write_text(item['title'] + '\n\n' + '\n\n'.join(value for _,_,value in cues)
                          + f"\n\nEvidence: {item.get('source_url', item.get('source_path', ''))}\n",
                          encoding='utf-8')
    return {'id': item['id'], 'video': item['video'], 'bytes': video.stat().st_size,
            'sha256': sha256(video), 'duration_seconds': DURATION,
            'evidence_kind': item['evidence_kind'], 'source_path': item.get('source_path'),
            'source_sha256': item.get('provenance', {}).get('source_sha256')}


def verify(items: list[dict], site: Path) -> list[dict]:
    results = []
    for item in items:
        video = site/item['video']
        data = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
            'stream=codec_name,width,height,pix_fmt:format=duration,size',
            '-of', 'json', str(video)], text=True))
        stream = data['streams'][0]
        assert stream['codec_name'] == 'h264', (item['id'], stream)
        assert stream['pix_fmt'] == 'yuv420p', (item['id'], stream)
        assert (stream['width'], stream['height']) == (WIDTH, HEIGHT)
        assert abs(float(data['format']['duration']) - DURATION) < .1
        raw = video.read_bytes()
        assert raw.index(b'moov') < raw.index(b'mdat'), item['id']
        for key in ('poster', 'captions'):
            assert (site/item[key]).is_file(), (item['id'], key)
        assert (site/item['captions']).read_text().startswith('WEBVTT\n')
        Image.open(site/item['poster']).verify()
        results.append({'id': item['id'], 'codec': 'h264', 'width': WIDTH, 'height': HEIGHT,
                        'duration_seconds': float(data['format']['duration']),
                        'bytes': int(data['format']['size']), 'sha256': sha256(video),
                        'faststart': True, 'evidence_kind': item['evidence_kind'],
                        'model_label': item.get('model_label'),
                        'source_path': item.get('source_path'),
                        'source_sha256': item.get('source_sha256')})
    return results



def render_overview(items: list[dict], site: Path) -> dict:
    """Concatenate labeled, retimed excerpts; preserve each clip's evidence stamp."""
    video = site/'media/open-jev-overview.mp4'
    seconds_per_item = 2.5
    with tempfile.TemporaryDirectory(prefix='open-jev-overview-') as directory:
        temporary = Path(directory)
        segments = []
        for index, item in enumerate(items):
            segment = temporary/f'{index:03d}.mp4'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                            '-ss', '8.5', '-i', str(site/item['video']), '-t', str(seconds_per_item),
                            '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
                            '-pix_fmt', 'yuv420p', '-threads', '2', str(segment)], check=True)
            segments.append(segment)
        concat = temporary/'concat.txt'
        concat.write_text(''.join(f"file '{segment.as_posix()}'\n" for segment in segments))
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'concat', '-safe', '0', '-i', str(concat), '-c', 'copy',
                        '-movflags', '+faststart', str(video)], check=True)
    poster_item = next((item for item in items if item.get('visual_kind') == 'snake'), items[0])
    make_frame(poster_item, 9).save(site/'media/open-jev-overview.jpg', quality=88, optimize=True)
    cues = []
    for index, item in enumerate(items):
        evidence = 'Saved model replay.' if item['evidence_kind'] == 'model_replay' else 'Interface only; no inference.'
        cues.append((index*seconds_per_item, (index+1)*seconds_per_item,
                     f"{item['title']}. {evidence} Excerpt; see the individual video for context and limits."))
    (site/'media/open-jev-overview.vtt').write_text('WEBVTT\n\n' + '\n\n'.join(
        f'{timestamp(start)} --> {timestamp(end)}\n{value}' for start,end,value in cues)+'\n')
    (site/'media/open-jev-overview.txt').write_text('Open-Jev domain overview\n\n'
        'Retimed excerpts from every gallery video. Each domain preserves its evidence label.\n\n'
        + '\n'.join(f'{timestamp(start)} {value}' for start,_,value in cues)+'\n')
    return overview_info(video, len(items))


def overview_info(video: Path, count: int) -> dict:
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
              'stream=codec_name,width,height,pix_fmt:format=duration', '-of', 'json', str(video)], text=True))
    stream = probe['streams'][0]
    assert stream['codec_name'] == 'h264'
    assert stream['pix_fmt'] == 'yuv420p'
    assert (stream['width'], stream['height']) == (WIDTH, HEIGHT)
    assert abs(float(probe['format']['duration'])-count*2.5) < .2
    raw = video.read_bytes()
    assert raw.index(b'moov') < raw.index(b'mdat')
    return {'video': 'media/open-jev-overview.mp4', 'bytes': video.stat().st_size,
            'sha256': sha256(video), 'duration_seconds': float(probe['format']['duration']),
            'domain_excerpts': count, 'seconds_per_excerpt': 2.5,
            'codec': 'h264', 'pixel_format': 'yuv420p', 'width': WIDTH, 'height': HEIGHT,
            'faststart': True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT/'site/catalog.json')
    parser.add_argument('--site', type=Path, default=ROOT/'site')
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    for executable in ('ffmpeg', 'ffprobe'):
        if not shutil.which(executable):
            raise RuntimeError(f'{executable} must be installed and available on PATH')
    catalog = json.loads(args.catalog.read_text())
    # A gameplay attachment keeps the original technical view's asset paths.
    # Regenerating this renderer must never overwrite complete game recordings.
    items = [{**item, **item.get('decision_view', {})} for item in catalog['items']
             if not args.ids or item['id'] in args.ids]
    if not items:
        raise RuntimeError('No catalog entries selected')
    if not args.verify_only:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for result in pool.map(render_one, [(item, str(args.site)) for item in items]):
                print(json.dumps(result), flush=True)
    checked = verify(items, args.site)
    total = sum(row['bytes'] for row in checked)
    report = {'catalog_sha256': sha256(args.catalog), 'renderer_sha256': sha256(Path(__file__)),
              'count': len(checked), 'total_video_bytes': total, 'videos': checked,
              'font_path': font_file(), 'fps': FPS, 'audio': False,
              'caption_language': 'en', 'visualization': 'Source-based state diagrams and typed decision replay; not original screen recordings.'}
    if not args.ids:
        if not args.verify_only:
            report['overview'] = render_overview(items, args.site)
        else:
            report['overview'] = overview_info(args.site/'media/open-jev-overview.mp4', len(items))
        (args.site/'media/verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Verified {len(checked)} clips, {total/1024/1024:.2f} MiB of MP4 media.')


if __name__ == '__main__':
    main()
