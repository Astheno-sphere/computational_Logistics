"""Score fixed labelled provider cases; never grade unlabelled demonstrations."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path


def selected_index(sample, gold):
    if not sample['success']:
        return None
    keys, kind = gold['answer_keys'], gold['kind']
    qid = gold.get('question_id', 'decision')
    if 'decisions' in sample:
        answer = sample['decisions'][qid]
        if kind == 'noul':
            return int(answer)
        if kind == 'score':
            return answer
        return keys.index(answer)
    if 'archived_probabilities' in sample:
        values = sample['archived_probabilities']
    else:
        answer = sample['response']['answers'][qid]
        if kind == 'choice':
            return keys.index(answer['choice'])
        values = [1-answer['noul'], answer['noul']] if kind == 'noul' else [answer['probabilities'][k] for k in keys]
    return max(range(len(values)), key=values.__getitem__)


def categorical_sample(sample, gold):
    """Keep a usable discrete answer despite a strict probability-mass failure.

    Raw success/error and probabilities remain unchanged in the source file.
    This is a separate decision-only analysis, not probability validation.
    """
    if sample['success'] or sample.get('http_status') != 200 or sample.get('error') != 'probabilities do not sum to one':
        return sample
    response = sample.get('response', {})
    if response.get('model') != sample['mode']:
        return sample
    qid = gold.get('question_id', 'decision')
    answers = response.get('answers', {})
    if qid not in answers:
        return sample
    answer = answers[qid]
    if answer.get('type') != gold['kind'] or gold['kind'] not in ('choice', 'score'):
        return sample
    probabilities = answer.get('probabilities', {})
    if set(probabilities) != set(gold['answer_keys']):
        return sample
    values = list(probabilities.values())
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values) or not sum(values) > 0:
        return sample
    if gold['kind'] == 'choice' and (answer.get('choice') not in probabilities or probabilities[answer['choice']] != max(values)):
        return sample
    return {**sample, 'success': True, 'strict_probability_mass_failure': True}


def summarize(golds, samples, *, categorical_only=False):
    if len({(row['request_id'],row.get('question_id','decision')) for row in golds}) != len(golds):
        raise ValueError('Duplicate gold question identity')
    by_id = {}
    for row in samples:
        if row.get('phase') != 'measured':
            continue
        if row['request_id'] in by_id:
            raise ValueError('Quality suite requires exactly one attempt per fixed request')
        by_id[row['request_id']] = row
    scored, pending = [], []
    for gold in golds:
        sample = by_id.get(gold['request_id'])
        if sample is None:
            pending.append(gold['request_id'])
            continue
        if sample['request_sha256'] != gold['request_sha256']:
            raise ValueError('Sample was measured on another request')
        if categorical_only:
            sample = categorical_sample(sample, gold)
        target = gold['target']
        if type(target) is int:
            distribution = [float(i == target) for i in range(len(gold['answer_keys']))]
        else:
            distribution = target
        hard = sum(value == 1 for value in distribution) == 1 and all(value in (0, 1) for value in distribution)
        index = selected_index(sample, gold)
        expected = 0.0 if index is None else distribution[index]
        scored.append({'request_id': gold['request_id'], 'question_id': gold.get('question_id','decision'),
                       'source': gold['source'], 'split': gold['split'],
                       'group_id': gold['group_id'], 'kind': gold['kind'], 'success': sample['success'],
                       'hard_target': hard, 'selected_index': index, 'target': target,
                       'expected_accuracy_contribution': expected,
                       'correct': bool(expected == 1) if hard else None})
        scored[-1]['strict_probability_mass_failure'] = sample.get('strict_probability_mass_failure',False)

    def aggregate(rows):
        hard = [row for row in rows if row['hard_target']]
        return {'evaluated':len(rows), 'successful_responses':sum(row['success'] for row in rows),
                'errors':sum(not row['success'] for row in rows), 'hard_targets':len(hard),
                'usable_decisions_with_probability_mass_failure':sum(row['strict_probability_mass_failure'] for row in rows),
                'hard_correct':sum(row['correct'] for row in hard),
                'hard_accuracy_including_errors':sum(row['correct'] for row in hard)/len(hard) if hard else None,
                'soft_targets':len(rows)-len(hard),
                'expected_accuracy_including_errors':sum(row['expected_accuracy_contribution'] for row in rows)/len(rows) if rows else None}
    sources = defaultdict(list)
    for row in scored:
        sources[row['source']].append(row)
    return {'status': 'complete' if not pending else 'partial', 'unit':'typed_decision',
            'planned_labelled_decisions':len(golds), 'planned_requests':len({g['request_id'] for g in golds}),
            'pending_count':len(pending), 'pending_request_ids':sorted(set(pending)), 'overall':aggregate(scored),
            'by_source': {source:aggregate(rows) for source,rows in sorted(sources.items())},
            'rows':scored,
            'categorical_only_analysis':categorical_only,
            'scope':'Fixed deterministic coverage cases, not population accuracy. Failed requests count zero; missing requests remain pending. Soft targets contribute expected accuracy and are excluded from hard accuracy. Categorical Score compares most probable level; it is not a calibrated expected-score comparison. When categorical-only is enabled, usable finite Choice/Score decisions with non-unit probability mass are counted separately; raw strict validation results are preserved, and probabilities are not normalized or scored.'}


def import_archived(root, tag, golds):
    """Reuse only byte-bound, exact-row historical evidence, without latency."""
    root = Path(root)
    audit = json.loads((root/'reports/full-data-eval-n1-v1'/f'{tag}-audit.json').read_bytes())
    if audit['status'] != 'passed' or not audit['model_evaluation_complete']:
        raise ValueError('Archived audit did not pass')
    wanted = {row['record_id']:row for row in golds}
    samples = []
    for split in ('test','ood'):
        name = f'merged-{split}.jsonl'
        raw = (root/'runs/full-data-eval-n1-v1'/tag/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != audit['verification']['source_files'][name]['sha256']:
            raise ValueError('Archived prediction hash differs')
        for line in raw.splitlines():
            row = json.loads(line)
            gold = wanted.get(row['id'])
            if not gold:
                continue
            if row['row_sha256'] != gold['row_sha256']:
                # The expanded profile may have changed a row: do not reuse it.
                continue
            if row['target'] != gold['target'] or row['checkpoint']['checkpoint_sha256'] != audit['checkpoint']['checkpoint_sha256']:
                raise ValueError('Archive checkpoint/target mismatch')
            sample = {'request_id':gold['request_id'], 'request_sha256':gold['request_sha256'],
                      'phase':'measured', 'repetition':0, 'success':row['status']=='ok',
                      'mode':'Open-Jev-'+tag+'-archived', 'provenance':'historical_prediction_exact_row_sha256_match_not_new_inference',
                      'checkpoint_sha256':audit['checkpoint']['checkpoint_sha256'], 'row_sha256':row['row_sha256']}
            if sample['success']:
                sample['archived_probabilities'] = row['probabilities']
            samples.append(sample)
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold', required=True, type=Path)
    parser.add_argument('--samples', type=Path)
    parser.add_argument('--archive', choices=('2b','9b'))
    parser.add_argument('--categorical-only', action='store_true')
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if bool(args.samples) == bool(args.archive):
        parser.error('Provide samples or archive, exactly one')
    golds = json.loads(args.gold.read_bytes())['rows']
    samples = import_archived(args.root,args.archive,golds) if args.archive else [json.loads(line) for line in args.samples.read_bytes().splitlines() if line.strip()]
    report = summarize(golds,samples,categorical_only=args.categorical_only)
    report['provider'] = 'Open-Jev-'+args.archive+'-archived' if args.archive else sorted({row['mode'] for row in samples})
    report['gold_sha256'] = hashlib.sha256(args.gold.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'overall':report['overall'],'pending_count':report['pending_count']}))


if __name__ == '__main__':
    raise SystemExit(main())
