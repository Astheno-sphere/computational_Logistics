"""Verify saved transcript labels from visible segment text, without importing the generator."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from jev.api import compile_request
from jev.data import SPLITS, validate_records

# This recognizes the documented controlled grammar, not arbitrary web transcripts.
RULES = {
    'other': r'inaudible|fragment|unintelligible|wordless|silent transition|no speech|audio cannot be understood|unresolved whether|not been confirmed',
    'self_promo': r'our own store|our own membership program|subscribe to my channel|my own course|belongs to me, the creator|press the like button|community I run',
    'sponsor': r'paid for by .+independent company|third-party sponsor paying|received payment from the unrelated company|external advertiser.+bought this placement|commissioned and financed by|underwritten by the outside business|purchased this advertising slot',
    'intro': r'hello and welcome|today we begin|welcome back, everyone|before the lesson starts|opening of our episode',
    'outro': r'concludes this video|reached the end of the episode|time is up for today|recording is over|recording to a close',
    'recap': r'to recap what we covered|summary of our earlier steps|key points already discussed|looking back over the explanation|retrospective of the preceding demonstration',
    'content': r'tested .+independently|independent review|discount code .+worked example|no company funded this review|neither money nor gifts|received no compensation for this evaluation|no commercial relationship exists|to investigate .+change one setting|place the two measurements|demonstration repeats the procedure|vary the selected parameter|procedure estimates change',
}


def classify_visible_segment(text):
    matches = [label for label, pattern in RULES.items() if re.search(pattern, text, re.I)]
    if len(matches) != 1:
        raise ValueError(f'Unrecognized or ambiguous controlled speech function: {matches}')
    return matches[0]


def audit(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, expected in manifest['files_sha256'].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError('File hash mismatch: ' + name)
    rows = [json.loads(line) for split in SPLITS for line in (directory / f'{split}.jsonl').read_text().splitlines()]
    structure = validate_records(rows)
    by_id = {row['id']: row for row in rows}
    cases = [json.loads(line) for line in (directory / 'cases.jsonl').read_text().splitlines()]
    checked, labels, family_splits, variants = set(), Counter(), {}, {}
    for case in cases:
        group, split = case['group_id'], case['split']
        if group in family_splits and family_splits[group] != split:
            raise ValueError('Counterfactual family crosses splits')
        family_splits[group] = split
        variants.setdefault(group, set()).add(case['variant'])
        request = case['request']
        if set(request['state']) != {'video_title', 'channel', 'note', 'segments'}:
            raise ValueError('Unexpected model-visible field')
        segments = {segment['id']: segment for segment in request['state']['segments']}
        roles_by_brand = {}
        for segment in segments.values():
            if set(segment) != {'id', 'start', 'text', 'has_promo_markers'} or not re.fullmatch(r'\d+:[0-5]\d', segment['start']):
                raise ValueError('Segment contract or timestamp differs')
            role = classify_visible_segment(segment['text'])
            for brand in re.findall(r'Luma-[0-9a-f]+', segment['text']):
                roles_by_brand.setdefault(brand, set()).add(role)
        if any(len(roles) != 1 for roles in roles_by_brand.values()):
            raise ValueError('One brand has conflicting roles in shared video context')
        compiled = compile_request(**request)
        if len(compiled) != len(segments) or len(case['record_ids']) != len(compiled):
            raise ValueError('Segment/question/row coverage differs')
        for record_id, item in zip(case['record_ids'], compiled):
            row = by_id[record_id]
            if record_id in checked or row['group_id'] != group or row['split'] != split:
                raise ValueError('Duplicate or misgrouped row')
            sid = re.search(r'^Classify segment (\S+) by its principal', item['question']).group(1)
            expected = classify_visible_segment(segments[sid]['text'])
            if set(item['answer_keys']) != set(RULES):
                raise ValueError('Missing seven-way category')
            if any(row[key] != item[key] for key in ('state', 'question', 'kind', 'options')):
                raise ValueError('Stored training input differs from actual request')
            target = [float(key == expected) for key in item['answer_keys']]
            if row['target'] != target or case['reference_by_segment'][sid] != expected:
                raise ValueError('Label disagrees with visible segment')
            checked.add(record_id)
            labels[expected] += 1
    if checked != set(by_id) or any(value != {0, 1, 2} for value in variants.values()):
        raise ValueError('Incomplete family or row coverage')
    if (manifest['summary'] != structure or manifest['typed_rows'] != len(checked)
            or manifest['video_contexts'] != len(cases) or manifest['video_families'] != len(family_splits)
            or manifest['class_counts'] != dict(labels) or manifest['configuration']['groups'] != len(family_splits)
            or manifest['configuration']['ood_groups'] != sum(value == 'ood' for value in family_splits.values())):
        raise ValueError('Manifest counts differ from actual payload')
    return {'status': 'passed', 'rows': len(checked), 'families': len(family_splits),
            'video_contexts': len(cases), 'class_counts': dict(labels), 'structure': structure,
            'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'generator_imported': False, 'reference_metadata_used_to_derive_labels': False,
            'scope': 'Independent visible-text parser for the declared original grammar; not a general-purpose transcript classifier or model evaluation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.directory)
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered)
