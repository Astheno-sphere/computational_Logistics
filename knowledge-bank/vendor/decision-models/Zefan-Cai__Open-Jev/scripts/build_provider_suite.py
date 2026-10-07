"""Freeze all-domain provider inputs, with gold labels in a separate file.

Select a deterministic first coverage pass without observing any model output.
Also index every prepared test/OOD row for subsequent exhaustive evaluation.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from jev.api import candidate_prompts, compile_request
from scripts.benchmark_inference_latency import digest

CORPORA = (
    'browser-drone-expansion-v1', 'citation-control-v1', 'entity-alignment-control-v1',
    'amount-extraction-control-v1', 'email-selection-control-v1', 'phone-extraction-control-v1',
    'context-retention-control-v1', 'sponsor-segment-control-v1', 'silent-failure-control-v1',
)


def request_for_row(row):
    """Round-trip candidate text exactly; metadata and target are never inputs."""
    definition = {'type': row['kind'], 'instructions': row['question']}
    if row['kind'] == 'choice':
        # Prefer the original key/description spelling where it is recoverable.
        pairs = [option.split(': ', 1) for option in row['options']]
        if all(len(pair) == 2 for pair in pairs) and len({pair[0] for pair in pairs}) == len(pairs):
            definition['criteria'] = {pair[0]: pair[1] for pair in pairs}
        else:
            definition['criteria'] = dict.fromkeys(row['options'])
    elif row['kind'] == 'score':
        definition['criteria'] = row['options']
    request = {'state': row['state'], 'questions': {'decision': definition}}
    compiled = compile_request(request['state'], request['questions'])[0]
    if candidate_prompts(compiled) != candidate_prompts(row):
        raise ValueError('Candidate prompt round-trip changed input: ' + row['id'])
    return request, compiled['answer_keys']


def workload_for_row(row):
    request, keys = request_for_row(row)
    workload = {'id': 'heldout-' + digest([row['source'], row['id']])[:24],
                'kind': 'heldout_decision', 'request': request, 'request_sha256': digest(request)}
    gold = {'request_id': workload['id'], 'record_id': row['id'], 'source': row['source'],
            'split': row['split'], 'group_id': row['group_id'], 'kind': row['kind'],
            'target': row['target'], 'answer_keys': keys, 'row_sha256': digest(row),
            'request_sha256': workload['request_sha256']}
    return workload, gold


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path('data'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--examples', type=Path, default=Path('examples'))
    parser.add_argument('--per-stratum', type=int, default=2)
    parser.add_argument('--extra-corpus', action='append', default=[],
                        help='Append a reviewed corpus without changing the frozen default suite')
    args = parser.parse_args()
    if not 1 <= args.per_stratum <= 100:
        parser.error('per-stratum must be 1–100')
    corpora = [*CORPORA, *args.extra_corpus]
    if len(corpora) != len(set(corpora)) or any(Path(name).name != name for name in corpora):
        parser.error('Corpus names must be unique direct children of data-root')
    args.output.mkdir(parents=True, exist_ok=False)
    strata, counts, manifests = defaultdict(list), Counter(), []
    seen = set()
    with (args.output/'all-heldout.jsonl').open('x') as all_rows:
        for name in corpora:
            directory = args.data_root/name
            raw_manifest = (directory/'manifest.json').read_bytes()
            manifest = json.loads(raw_manifest)
            hashes = manifest.get('sha256', manifest.get('files_sha256'))
            if not hashes:
                raise ValueError('Manifest missing file hashes: ' + name)
            identity = {'corpus': name, 'manifest_sha256': hashlib.sha256(raw_manifest).hexdigest(), 'splits': {}}
            for split in ('test', 'ood'):
                raw = (directory/(split+'.jsonl')).read_bytes()
                expected = hashes.get(split, hashes.get(split+'.jsonl'))
                if hashlib.sha256(raw).hexdigest() != expected:
                    raise ValueError('Frozen split hash differs: ' + name + '/' + split)
                rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
                identity['splits'][split] = {'sha256': expected, 'rows': len(rows)}
                for row in rows:
                    if row['split'] != split or row['id'] in seen:
                        raise ValueError('Duplicate record or wrong split: ' + row['id'])
                    seen.add(row['id'])
                    workload, gold = workload_for_row(row)
                    counts[(row['source'], split, row['kind'])] += 1
                    all_rows.write(json.dumps({'workload': workload, 'gold': gold}, ensure_ascii=False) + '\n')
                    stratum = (row['source'], split, row['kind'])
                    strata[stratum].append((digest(['provider-coverage-v1', row['id']]), workload, gold))
            manifests.append(identity)
    selected, golds = [], []
    for key in sorted(strata):
        for _, workload, gold in sorted(strata[key], key=lambda v: v[0])[:args.per_stratum]:
            selected.append(workload); golds.append(gold)
    example_ids = []
    for path in sorted(args.examples.rglob('*.json')):
        value = json.loads(path.read_bytes())
        if not isinstance(value, dict) or not {'state', 'questions'} <= set(value):
            continue
        request = {key: value[key] for key in ('state', 'questions')}
        compile_request(request['state'], request['questions'])
        wid = 'example-' + path.relative_to(args.examples).with_suffix('').as_posix().replace('/', '-')
        selected.append({'id': wid, 'kind': 'saved_example_unlabelled', 'source_path': str(path),
                         'request': request, 'request_sha256': digest(request)})
        example_ids.append(wid)
    if len({row['id'] for row in selected}) != len(selected):
        raise ValueError('Duplicate workload ID')
    write_json(args.output/'requests.json', {'schema_version': 1, 'workloads': selected})
    write_json(args.output/'gold.json', {'schema_version': 1, 'rows': golds})
    report = {'schema_version': 1, 'status': 'frozen_not_yet_fully_evaluated',
              'selection': f'lowest SHA256(provider-coverage-v1, record_id), {args.per_stratum} per source/split/kind; no provider outputs consulted',
              'all_heldout_rows': len(seen), 'task_source_ids': len({key[0] for key in counts}),
              'coverage_pass_labelled': len(golds), 'coverage_pass_unlabelled_examples': len(example_ids),
              'coverage_pass_requests': len(selected), 'strata': [
                  {'source': k[0], 'split': k[1], 'kind': k[2], 'available': counts[k],
                   'selected': min(args.per_stratum, counts[k])} for k in sorted(counts)],
              'dataset_identities': manifests,
              'limitations': ['Initial stratified coverage is not the exhaustive test/OOD result.',
                  'Saved examples lack gold labels: report response validity and latency, not accuracy.',
                  'Snapshot decisions are not closed-loop gameplay, browser execution or flight.',
                  'JF100 rotations and TREC DL19/DL20 are separate held-out suites, not training data.',
                  'Full raw registry contains licensed Wikispeedia records; do not republish it. Rebuild from licensed original data.'],
              'files': {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                        for p in args.output.iterdir() if p.is_file()}}
    write_json(args.output/'manifest.json', report)
    print(json.dumps({k: report[k] for k in ('all_heldout_rows', 'task_source_ids', 'coverage_pass_requests', 'coverage_pass_labelled', 'coverage_pass_unlabelled_examples')}))


if __name__ == '__main__':
    main()
