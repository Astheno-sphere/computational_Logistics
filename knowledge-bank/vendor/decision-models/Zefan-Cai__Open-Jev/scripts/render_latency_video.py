"""Present actual benchmark logs as a site summary and captioned evidence video.

No inference is run here. The video uses the first measured HTTP request for
the explicitly selected workload; it does not select the fastest response.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS = 1280, 720, 24
INK, GREEN, MUTED, BG, PANEL = '#152032', '#247b52', '#56665c', '#f5f4ef', '#e6ece2'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_measurements(report_dir):
    report = read(report_dir / 'report.json')
    workloads = read(report_dir / 'requests.json')['workloads']
    samples = [json.loads(line) for line in (report_dir / 'samples.jsonl').read_text().splitlines()]
    digest = hashlib.sha256(json.dumps(workloads, ensure_ascii=False, sort_keys=True,
                                      separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if digest != report['workload_manifest_sha256']:
        raise ValueError('Workload manifest differs from the measured report')
    by_id = {row['id']: row for row in workloads}
    identities = [(row['request_id'], row['transport'], row['mode'], row['phase'], row['repetition']) for row in samples]
    if len(by_id) != len(workloads) or len(set(identities)) != len(samples):
        raise ValueError('Duplicate workload or raw attempt')
    for sample in samples:
        if sample['request_id'] not in by_id or sample['request_sha256'] != by_id[sample['request_id']]['request_sha256']:
            raise ValueError('Raw attempt request hash differs')
    keys = ('request_id', 'transport', 'mode')
    expected_groups = {tuple(item[key] for key in keys) for item in samples if item['phase'] == 'measured'}
    summary_groups = [tuple(row[key] for key in keys) for row in report['summaries']]
    if len(summary_groups) != len(set(summary_groups)) or set(summary_groups) != expected_groups:
        raise ValueError('Summary groups differ from the raw measurements')
    for row in report['summaries']:
        matching = [item for item in samples if item['phase'] == 'measured'
                    and all(item[key] == row[key] for key in keys)]
        times = sorted(item['wall_ms'] for item in matching if item['success'])
        if any(not math.isfinite(item['wall_ms']) or item['wall_ms'] < 0 for item in matching):
            raise ValueError('Invalid raw timing')
        if (len(matching), len(times), len(matching) - len(times)) != (row['attempts'], row['successes'], row['errors']):
            raise ValueError('Summary counts differ from the raw measurements')
        for field, quantile in [('p50_ms', .5), ('p95_ms', .95)]:
            if not times:
                if row[field] is not None:
                    raise ValueError('Empty measurement set has a numeric percentile')
                continue
            position = (len(times) - 1) * quantile
            computed = times[math.floor(position)] + (times[math.ceil(position)] - times[math.floor(position)]) * (position % 1)
            if not math.isclose(computed, row[field], abs_tol=1e-7):
                raise ValueError('Summary percentile differs from the raw measurements')
    if sum(item['phase'] == 'measured' for item in samples) != report['measured_attempts']:
        raise ValueError('Total measured attempts differ')
    if sum(not item['success'] for item in samples) != report['errors_including_warmup']:
        raise ValueError('Total errors differ')
    return report, workloads, samples


def export_summary(report_dir, request_id):
    report, workloads, samples = verify_measurements(report_dir)
    if report['checkpoint_model_config']['model_id'] != 'Qwen/Qwen3.5-2B':
        raise ValueError('This presentation is for the released Qwen3.5-2B checkpoint')
    if not report['summaries']:
        raise ValueError('Completed model measurements are required')
    # A fixed first attempt makes the example reproducible, regardless of timing.
    example_rows = [row for row in samples if row['request_id'] == request_id
                    and row['phase'] == 'measured' and row['transport'] == 'http_loopback'
                    and row['mode'] == 'uncached' and row['repetition'] == 0]
    if len(example_rows) != 1 or not example_rows[0]['success']:
        raise ValueError('Selected first measured example must be a successful actual response')
    sample = example_rows[0]
    workload = next(row for row in workloads if row['id'] == request_id)
    selected_summary = next(row for row in report['summaries'] if row['request_id'] == request_id
                            and row['transport'] == 'http_loopback' and row['mode'] == 'uncached')
    measured = [row['wall_ms'] for row in samples if row['request_id'] == request_id
                and row['phase'] == 'measured' and row['transport'] == 'http_loopback'
                and row['mode'] == 'uncached' and row['success']]
    raw_url = 'https://github.com/Zefan-Cai/Open-Jev/tree/main/' + report_dir.relative_to(ROOT).as_posix()
    labels = {'customer_service': 'Customer support', 'drone': 'Drone snapshot'}
    dtype_names = {'torch.bfloat16': 'BF16', 'torch.float16': 'FP16', 'torch.float32': 'FP32'}
    backbone_dtype = '/'.join(dtype_names.get(value, value) for value in report['runtime']['backbone_parameter_dtypes'])
    head_dtype = '/'.join(dtype_names.get(value, value) for value in report['runtime']['head_parameter_dtypes'])
    summary = {
        'schema_version': 1, 'measured_at': report['created_at'], 'status': report['status'],
        'model': 'Open-Jev-2B',
        'runtime': {key: report['runtime'][key] for key in ('gpu', 'torch', 'transformers', 'peft', 'attention_implementation')},
        'dtype': f'{backbone_dtype} · {head_dtype} head',
        'configuration': {name: report['configuration'][name] for name in ('warmup', 'repetitions', 'batch_size')},
        'scope': report['scope'], 'summaries': report['summaries'],
        'cache_comparisons': report['cache_comparisons'],
        'errors_including_warmup': report['errors_including_warmup'],
        'measured_attempts': report['measured_attempts'], 'warmup_attempts': report['warmup_attempts'],
        'cache_note': (f"The experimental cache path failed the {report['configuration']['max_probability_error']:.1g} probability-parity gate overall. Cached timings are diagnostic; they do not establish equivalent-output acceleration."
                       if any(not row['parity_passed'] for row in report['cache_comparisons']) else
                       f"All recorded cache pairs passed the {report['configuration']['max_probability_error']:.1g} probability-parity gate. Inspect each workload's timings separately."),
        'workloads': [{**{key: row[key] for key in ('id', 'kind', 'state_tokens', 'question_count',
                                                  'candidate_sequences', 'candidate_input_tokens')},
                       'label': labels.get(row['id'], f"Choice · {row['candidate_sequences']} candidates")}
                      for row in workloads],
        'jev': {'measured': False, 'inference_latency_ms': None, 'summaries': [],
                'status_text': 'No completed Jev API measurements are included in this report.'},
        'raw_report_url': raw_url,
        'source_sha256': {name: sha(report_dir / name) for name in ('report.json', 'requests.json', 'samples.jsonl')},
        'example': {'request_id': request_id, 'request': workload['request'], 'response': sample['response'],
                    'measured_wall_ms': sample['wall_ms'], 'transport': 'http_loopback', 'mode': 'uncached',
                    'repetition': 0, 'selection': 'First measured attempt; not selected by latency.'},
    }
    if (report_dir / 'publication.json').exists():
        summary['client_identity_sha256'] = read(report_dir / 'publication.json')['client_identity_sha256']
        summary['source_sha256']['publication.json'] = sha(report_dir / 'publication.json')
    return summary, workload, sample, selected_summary, measured


def add_provider_summary(summary, report_dir, local_report_dir, provider):
    report, workloads, samples = verify_measurements(report_dir)
    local_workloads = read(local_report_dir / 'requests.json')['workloads']
    local_by_id = {row['id']: row for row in local_workloads}
    if any(row != local_by_id.get(row['id']) for row in workloads):
        raise ValueError('Provider and Open-Jev request text or metadata differ')
    successes = sum(row['successes'] for row in report['summaries'])
    result = {
        'measured': successes > 0, 'model': report['model'], 'status': report['status'],
        'measured_at': report['created_at'], 'scope': report['scope'],
        'configuration': {key: report['configuration'][key] for key in ('warmup', 'repetitions')},
        'summaries': report['summaries'], 'errors_including_warmup': report['errors_including_warmup'],
        'measured_attempts': report['measured_attempts'], 'warmup_attempts': report['warmup_attempts'],
        'status_text': f"{report['model']}: {successes}/{report['measured_attempts']} timed requests returned valid responses, with {report['errors_including_warmup']} errors including warmup. Status: {report['status'].replace('_', ' ')}.",
        'raw_report_url': 'https://github.com/Zefan-Cai/Open-Jev/tree/main/' + report_dir.relative_to(ROOT).as_posix(),
        'source_sha256': {name: sha(report_dir / name) for name in ('report.json', 'requests.json', 'samples.jsonl')},
    }
    if (report_dir / 'publication.json').exists():
        result['client_identity_sha256'] = read(report_dir / 'publication.json')['client_identity_sha256']
        result['same_client_as_local'] = result['client_identity_sha256'] == summary.get('client_identity_sha256')
        if not result['same_client_as_local']:
            raise ValueError('Local and remote measurement clients differ')
        result['source_sha256']['publication.json'] = sha(report_dir / 'publication.json')
    if provider == 'openai':
        payloads = read(report_dir / 'payloads.json')
        payload_by_id = {row['id']: row['payload'] for row in payloads}
        if len(payloads) != len(workloads) or set(payload_by_id) != {row['id'] for row in workloads}:
            raise ValueError('OpenAI payload inventory differs')
        for row in workloads:
            payload = payload_by_id[row['id']]
            if payload['model'] != report['model'] or json.loads(payload['input']) != row['request']:
                raise ValueError('OpenAI payload differs from the shared task input')
        payload_hashes = {key: hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                          for key, value in payload_by_id.items()}
        if any(sample['payload_sha256'] != payload_hashes[sample['request_id']] for sample in samples):
            raise ValueError('OpenAI payload differs from the one used by a measured attempt')
        efforts = {payload['reasoning']['effort'] for payload in payload_by_id.values()}
        if len(efforts) != 1:
            raise ValueError('Mixed reasoning settings in one provider run')
        result['reasoning_effort'] = efforts.pop()
        result['source_sha256']['payloads.json'] = sha(report_dir / 'payloads.json')
        result['output_contract'] = 'Generated categorical decisions; not calibrated probabilities. Full response time includes generation.'
        summary.setdefault('openai', []).append(result)
    else:
        result['output_contract'] = 'Native typed probability response.'
        summary['jev'] = result
    example = next((row for row in samples if row['request_id'] == summary['example']['request_id']
                    and row['phase'] == 'measured' and row['repetition'] == 0), None)
    if example is not None:
        result['example'] = {key: example[key] for key in ('request_id', 'success', 'wall_ms', 'response', 'decisions') if key in example}


def font(size, bold=False):
    from PIL import ImageFont
    candidates = [Path('/System/Library/Fonts/Supplemental') / ('Arial Bold.ttf' if bold else 'Arial.ttf'),
                  Path('/usr/share/fonts/truetype/dejavu') / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    return ImageFont.truetype(str(next(path for path in candidates if path.exists())), size)


def validate_customer_example(workload, response):
    # This video's customer example has a settled charge and exact refund consent.
    # Check all policy decisions, not just the visually prominent refund answer.
    canonical = read(ROOT / 'examples/workflows/customer_service.json')
    if workload['request'] != canonical:
        raise ValueError('Video currently supports only the exact customer_service example')
    yes = {'SAY', 'REFUND', 'SET INTENT'}
    answers = response['answers']
    if set(answers) != set(canonical['questions']):
        raise ValueError('Customer example is incomplete')
    if any((answer['noul'] >= .5) != (key in yes) for key, answer in answers.items()):
        raise ValueError('Customer policy check failed; keep raw result, do not render a showcase video')


def render_frame(scene, summary, workload, sample, stats, measured):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(im)
    def text(x, y, value, size=28, color=INK, bold=False):
        draw.multiline_text((x, y), value, font=font(size, bold), fill=color, spacing=12)
    def label(value):
        text(60, 113, value.upper(), 21, GREEN, True)
    text(60, 28, '[J]  Open-Jev', 28, INK, True)
    text(829, 34, '2B / MEASURED REQUEST', 19, MUTED)
    draw.line((60, 83, 1220, 83), fill='#cbd4c8', width=2)
    gpu = summary['runtime']['gpu'].replace('NVIDIA ', '')
    if scene == 'request':
        label('Recorded customer support request')
        text(60, 173, '“Please refund\nthis charge.”', 65, INK, True)
        text(64, 370, 'Identity verified. Settled charge.\nRefund consent matches the proposal.', 29, MUTED)
        text(64, 505, f"{workload['state_tokens']} state tokens\n{workload['question_count']} independent questions · {workload['candidate_sequences']} input sequences", 26, GREEN)
        draw.rounded_rectangle((846, 181, 1217, 555), 20, fill=PANEL)
        text(874, 211, 'THE MEASUREMENT', 19, GREEN, True)
        text(874, 266, 'Warm 2B checkpoint\nLoopback HTTP\nCache off\nConcurrency 1', 26, INK)
        text(874, 459, gpu, 23, MUTED)
        text(874, 498, summary['dtype'].replace('torch.', ''), 23, MUTED)
    elif scene == 'response':
        label('Actual probabilities / first measured attempt')
        text(60, 174, f"{sample['wall_ms']:.1f} ms", 75, GREEN, True)
        text(64, 277, 'Complete HTTP request', 26, INK)
        text(64, 354, 'Includes tokenization, inference,\nJSON and local TCP transport.', 27, MUTED)
        text(64, 471, 'No model loading.\nNo public Internet transit.', 26, MUTED)
        for i, (key, answer) in enumerate(sample['response']['answers'].items()):
            y = 168 + i * 53
            draw.rounded_rectangle((714, y, 1215, y + 45), 7, fill=PANEL)
            text(730, y + 8, key, 23, INK)
            text(1080, y + 8, f"{answer['noul']:.1%}", 23, GREEN, True)
        text(720, 608, 'All 8 decisions match the stated policy.', 20, GREEN)
    elif scene == 'distribution':
        label('Every successful timed attempt / same request')
        text(60, 165, f"P50   {stats['p50_ms']:.1f} ms", 51, GREEN, True)
        text(60, 235, f"P95   {stats['p95_ms']:.1f} ms", 42, INK, True)
        config = summary['configuration']
        text(65, 320, f"{config['warmup']} warmups + {stats['attempts']} timed attempts\n{stats['errors']} failed timed requests", 27, MUTED)
        text(65, 445, 'One point per measured request.\nThe example is attempt 1,\nnot the fastest response.', 27, MUTED)
        left, top, right, bottom = 730, 209, 1194, 531
        ceiling = max(measured) * 1.13
        draw.line((left, top, left, bottom, right, bottom), fill='#a8b7a1', width=2)
        tick_step = 10 ** math.floor(math.log10(ceiling)) / 2
        for tick in range(math.floor(ceiling / tick_step) + 1):
            value = tick * tick_step
            y = bottom - (bottom - top) * value / ceiling
            draw.line((left, y, right, y), fill='#d3dbcf', width=1)
            text(left - 48, y - 10, f'{value:g}', 17, MUTED)
        for i, value in enumerate(measured):
            x = left + 20 + i * (right - left - 40) / max(1, len(measured) - 1)
            y = bottom - (bottom - top) * value / ceiling
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=GREEN)
        mid = bottom - (bottom - top) * stats['p50_ms'] / ceiling
        draw.line((left, mid, right, mid), fill='#a0b896', width=2)
        text(left + 7, mid - 31, 'P50', 19, MUTED)
        text(732, 565, '1                       request                       ' + str(len(measured)), 20, MUTED)
        text(733, 166, 'Measured wall time (ms)', 22, MUTED)
    elif scene == 'comparison':
        label('Open-Jev-2B vs Jev API')
        jev = next((row for row in summary['jev']['summaries'] if row['request_id'] == workload['id']), None)
        if jev and jev['successes']:
            text(65, 176, 'Same customer-support state and 8 questions', 30, INK, True)
            text(65, 238, 'Complete request', 23, MUTED)
            text(708, 238, 'P50', 23, MUTED)
            text(965, 238, 'P95', 23, MUTED)
            for i, (name, row) in enumerate([('2B · loopback HTTP', stats), ('Jev · fresh HTTPS', jev)]):
                y = 289 + 82 * i
                text(65, y, name, 30, INK, True)
                text(708, y, f"{row['p50_ms']:.1f} ms", 32, GREEN, True)
                text(965, y, f"{row['p95_ms']:.1f} ms", 32, GREEN, True)
            text(65, 462, f"n={stats['attempts']} local / {jev['attempts']} Jev · different network / backend costs", 25, MUTED)
        else:
            text(60, 178, 'Jev API: not measured.', 59, INK, True)
            text(65, 280, 'No successful measured API responses\nare included in this evidence video.', 31, MUTED)
            text(65, 412, 'Local HTTP and a hosted API have different\nnetwork and scheduling costs.', 29, MUTED)
        text(65, 517, 'Raw timings, exact requests and reproduction:', 24, GREEN)
        text(65, 566, 'zefan-cai.github.io/open-jev/#latency', 31, GREEN, True)
    elif scene == 'generation':
        label('The same decision task through text generation')
        text(65, 175, 'Full response latency · not first token', 35, INK, True)
        for i, provider in enumerate(summary.get('openai', [])):
            row = next((row for row in provider['summaries'] if row['request_id'] == workload['id']), None)
            if row and row['successes']:
                y = 263 + i * 113
                text(65, y, provider['model'], 29, INK, True)
                text(65, y + 44, 'Reasoning: ' + provider['reasoning_effort'], 22, MUTED)
                text(675, y, f"P50 {row['p50_ms']:.1f} ms", 30, GREEN, True)
                text(675, y + 44, f"P95 {row['p95_ms']:.1f} ms · n={row['attempts']}", 22, MUTED)
        text(65, 520, 'OpenAI: generated structured choices.\nOpen-Jev / Jev: direct typed probabilities.', 27, MUTED)
        text(65, 605, 'Different output contracts and remote backends.', 24, GREEN)
        text(739, 610, 'zefan-cai.github.io/open-jev/#latency', 19, GREEN, True)
    text(60, 674, 'Recorded benchmark evidence · video playback is not a live inference timer', 19, MUTED)
    return im


def render_video(summary, workload, sample, stats, measured, media_dir):
    validate_customer_example(workload, sample['response'])
    media_dir.mkdir(parents=True, exist_ok=True)
    stem = 'open-jev-2b-latency'
    target = media_dir / (stem + '.mp4')
    scenes = [('request', 7), ('response', 9), ('distribution', 8), ('comparison', 8)]
    if any(any(row['request_id'] == workload['id'] and row['successes'] for row in provider['summaries'])
           for provider in summary.get('openai', [])):
        scenes.append(('generation', 8))
    duration = sum(seconds for _, seconds in scenes)
    process = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
                                '-g', '48', '-an', '-movflags', '+faststart', str(target)], stdin=subprocess.PIPE)
    try:
        for scene, seconds in scenes:
            frame = render_frame(scene, summary, workload, sample, stats, measured)
            frame.save(media_dir / f'{stem}-{scene}.jpg', quality=94)
            raw = frame.tobytes()
            for _ in range(seconds * FPS):
                process.stdin.write(raw)
        process.stdin.close()
        if process.wait():
            raise RuntimeError('Video encoder failed')
    except BaseException:
        process.kill()
        process.wait()
        raise
    captions = [
        (0, 7, f"Released Open-Jev-2B. Customer support: {workload['state_tokens']} state tokens, {workload['question_count']} questions, {workload['candidate_sequences']} input sequences."),
        (7, 16, f"First measured request: {sample['wall_ms']:.1f} ms over loopback HTTP, cache off. All eight decisions match the policy."),
        (16, 24, f"{stats['attempts']} timed attempts: P50 {stats['p50_ms']:.1f} ms; P95 {stats['p95_ms']:.1f} ms; {stats['errors']} failed requests."),
        (24, 32, 'Same customer-support workload: local 2B uses loopback HTTP; Jev uses fresh HTTPS. Network and backend costs differ; this is not a matched-hardware speedup.'),
    ]
    if duration > 32:
        captions.append((32, 40, 'OpenAI returns generated structured decisions, not calibrated probabilities. Reported time includes the full response, not just the first token.'))
    def stamp(seconds):
        return f'00:00:{seconds:02d}.000'
    (media_dir / (stem + '.vtt')).write_text('WEBVTT\n\n' + '\n\n'.join(
        f'{stamp(a)} --> {stamp(b)} line:90%\n{caption}' for a, b, caption in captions) + '\n')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(target)], text=True))
    stream = next(item for item in probe['streams'] if item['codec_type'] == 'video')
    assert float(probe['format']['duration']) == duration and int(stream['nb_frames']) == duration * FPS
    asset_prefix = media_dir.relative_to(ROOT / 'site').as_posix() + '/'
    summary['video'] = {'path': asset_prefix + target.name, 'poster': f'{asset_prefix}{stem}-response.jpg',
                        'captions': f'{asset_prefix}{stem}.vtt', 'seconds': duration, 'sha256': sha(target),
                        'caption': 'Actual first measured customer-support response. Loopback HTTP, cache off; all eight policy decisions checked. Video playback is a presentation of the saved evidence.',
                        'renderer_sha256': sha(Path(__file__))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--request-id', default='customer_service')
    parser.add_argument('--jev-report', type=Path)
    parser.add_argument('--openai-report', type=Path, action='append', default=[])
    parser.add_argument('--site-summary', type=Path, default=ROOT / 'site/latency.json')
    parser.add_argument('--media-dir', type=Path, default=ROOT / 'site/latency-media')
    parser.add_argument('--video', action='store_true')
    args = parser.parse_args()
    summary, workload, sample, stats, measured = export_summary(args.report.resolve(), args.request_id)
    if args.jev_report:
        add_provider_summary(summary, args.jev_report.resolve(), args.report.resolve(), 'jev')
    for report in args.openai_report:
        add_provider_summary(summary, report.resolve(), args.report.resolve(), 'openai')
    if args.video:
        render_video(summary, workload, sample, stats, measured, args.media_dir)
    args.site_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    print(json.dumps({'summary': str(args.site_summary), 'video': summary.get('video', {}).get('path')}))


if __name__ == '__main__':
    main()
