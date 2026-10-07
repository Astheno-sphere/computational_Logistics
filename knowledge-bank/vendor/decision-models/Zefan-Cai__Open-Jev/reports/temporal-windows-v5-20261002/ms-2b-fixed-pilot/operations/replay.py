"""CPU replay from raw logits; imports neither the training runner nor Jev metrics."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def probabilities(row, temperature):
    maximum = max(row['logits'])
    values = [math.exp((x - maximum) / temperature) for x in row['logits']]
    return [x / sum(values) for x in values]


def status(row, temperature):
    yes = probabilities(row, temperature)[1]
    return 'no' if yes <= .2 else 'yes' if yes >= .8 else 'abstained'


def basic(rows, temperature):
    bins = [[] for _ in range(15)]
    correct = 0
    nll = brier = 0.
    for row in rows:
        probs = probabilities(row, temperature)
        truth = row['target'].index(1.)
        prediction = max(range(len(probs)), key=probs.__getitem__)
        correct += prediction == truth
        nll -= math.log(max(probs[truth], 1e-15))
        brier += sum((p - float(index == truth)) ** 2 for index, p in enumerate(probs))
        bins[min(14, int(probs[prediction] * 15))].append((probs[prediction], prediction == truth))
    ece = sum(abs(sum(x[0] for x in bucket) - sum(x[1] for x in bucket)) for bucket in bins)
    return dict(count=len(rows), accuracy=correct/len(rows), nll=nll/len(rows),
                brier=brier/len(rows), multiclass_ece=ece/len(rows))


def metrics(rows, temperature):
    result = basic(rows, temperature)
    for field in ('family', 'kind'):
        result['by_' + field] = {value: basic([r for r in rows if r[field] == value], temperature)
                                for value in sorted({r[field] for r in rows})}
    noul = [r for r in rows if r['kind'] == 'noul']
    decisions = [status(r, temperature) for r in noul]
    accepted = sum(x != 'abstained' for x in decisions)
    correct = sum(x == ('yes' if r['target'][1] else 'no') for x, r in zip(decisions, noul))
    result['noul_thresholds_0.2_0.8'] = dict(n=len(noul), correct=correct,
        accuracy=correct/len(noul) if noul else None, accepted=accepted,
        coverage=accepted/len(noul) if noul else None, abstentions=len(noul)-accepted,
        error_among_accepted=(accepted-correct)/accepted if accepted else None)
    return result


def combinations(before, after, released, trained):
    return {weight + '_logits_at_' + calibration + '_temperature': metrics(rows, temperature)
            for weight, rows in (('baseline', before), ('trained', after))
            for calibration, temperature in (('released', released), ('trained', trained))}


def paired(before, after, released, trained):
    assert [r['id'] for r in before] == [r['id'] for r in after]
    result = dict(n=len(before), correct_to_correct=0, incorrect_to_correct=0,
        correct_to_incorrect=0, incorrect_to_incorrect=0, argmax_changed=0,
        noul_status_transitions={})
    for a, b in zip(before, after):
        assert a['target'] == b['target'] and a['kind'] == b['kind']
        truth = a['target'].index(1.)
        p, q = (max(range(len(r['logits'])), key=r['logits'].__getitem__) for r in (a, b))
        result[('correct' if p == truth else 'incorrect') + '_to_' + ('correct' if q == truth else 'incorrect')] += 1
        result['argmax_changed'] += p != q
        if a['kind'] == 'noul':
            key = status(a, released) + '_to_' + status(b, trained)
            result['noul_status_transitions'][key] = result['noul_status_transitions'].get(key, 0) + 1
    return result


def compare(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys(), (a.keys(), b.keys())
        for key in a:
            compare(a[key], b[key])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            compare(x, y)
    elif isinstance(a, (int, float)):
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), (a, b)
    else:
        assert a == b, (a, b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--previous-v4', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pilot = root / 'pilot'
    manifest = json.loads((root / 'artifact-manifest.json').read_text())
    for name, proof in manifest.items():
        content = (root/name).read_bytes()
        assert len(content) == proof['bytes']
        assert hashlib.sha256(content).hexdigest() == proof['sha256'], name
    summary = json.loads((pilot / 'summary.json').read_text())
    released, trained = summary['released_temperature'], summary['trained_temperature']
    checked = 0
    for path in pilot.rglob('*.jsonl'):
        if path.name == 'training.jsonl':
            continue
        for row in read(path):
            compare(probabilities(row, row['temperature']), row['probabilities'])
            checked += 1
    training = read(pilot / 'adaptation/training.jsonl')
    assert [r['step'] for r in training] == list(range(1, 65))
    assert all(math.isfinite(r['loss']) and math.isfinite(r['gradient_norm']) for r in training)
    assert summary['steps'] == 64 and summary['training_rows_consumed'] == 256
    assert summary['distinct_training_rows'] == 128
    result, transitions, subgroups, drift, actions = {}, {}, {}, {}, {}
    for split in ('test', 'ood'):
        v5_before = read(pilot / ('adaptation/baseline_' + split + '.jsonl'))
        v5_after = read(pilot / ('adaptation/trained_' + split + '.jsonl'))
        v4_before = read(pilot / ('baseline_v4_' + split + '.jsonl'))
        v4_after = read(pilot / ('trained_v4_' + split + '.jsonl'))
        for family, before, after in (('v5', v5_before, v5_after), ('v4', v4_before, v4_after)):
            key = family + '_' + split
            result[key] = combinations(before, after, released, trained)
            transitions[key] = paired(before, after, released, trained)
        data = {r['id']: r for r in read(Path(args.dataset)/(split + '.jsonl'))}
        groups = {'boundary': {}, 'offset_pair': {}}
        for prediction in v5_before:
            state = data[prediction['id']]['state']
            delta = (datetime.fromisoformat(state['request_received_at']) - datetime.fromisoformat(state['delivered_at'])).total_seconds()
            deadline = state['return_window_hours'] * 3600
            boundary = ('exception' if state['exception_approved'] else 'before_delivery' if delta < 0
                else 'at_delivery' if delta == 0 else 'inside_window' if delta < deadline
                else 'at_deadline' if delta == deadline else 'after_deadline')
            offsets = state['delivered_at'][-6:] + ' to ' + state['request_received_at'][-6:]
            for field, label in (('boundary', boundary), ('offset_pair', offsets)):
                groups[field].setdefault(label, set()).add(prediction['id'])
        subgroups[split] = {field: {label: combinations([r for r in v5_before if r['id'] in ids],
            [r for r in v5_after if r['id'] in ids], released, trained) for label, ids in values.items()}
            for field, values in groups.items()}
        outside = groups['boundary']['before_delivery'] | groups['boundary']['after_deadline']
        actions[split] = {}
        for weight, rows in (('baseline', v5_before), ('trained', v5_after)):
            choice_actions, noul = {}, []
            for prediction in rows:
                if prediction['id'] not in outside:
                    continue
                row = data[prediction['id']]
                index = max(range(len(prediction['logits'])), key=prediction['logits'].__getitem__)
                decision = row['options'][index]
                if row['kind'] == 'choice':
                    assert row['options'][row['target'].index(1.)] == 'reject'
                    choice_actions[decision] = choice_actions.get(decision, 0) + 1
                else:
                    noul.append({'id': row['id'], 'proposal': row['question'], 'predicted': decision,
                                 'gold': row['options'][row['target'].index(1.)]})
            actions[split][weight] = {'outside_choice_predicted_actions': choice_actions,
                                     'outside_noul_argmax': noul}
        previous = {r['id']: r for r in read(Path(args.previous_v4)/('baseline_' + split + '.jsonl'))}
        changed = []
        old_correct = new_correct = 0
        for row in v4_before:
            old = previous[row['id']]
            assert old['target'] == row['target']
            truth = row['target'].index(1.)
            p, q = (max(range(len(r['logits'])), key=r['logits'].__getitem__) for r in (old, row))
            old_correct += p == truth
            new_correct += q == truth
            if p != q:
                changed.append({'id': row['id'], 'previous_prediction': p, 'current_prediction': q, 'truth': truth})
        drift[split] = {'n':len(v4_before), 'previous_correct':old_correct, 'current_correct':new_correct,
                        'argmax_changed':len(changed), 'changed_rows':changed}
    compare(result, summary['metrics'])
    compare(transitions, summary['paired_decisions'])
    compare(subgroups, summary['boundary_offset_results'])
    receipt = dict(status='independent_cpu_replay_passed',artifact_hashes_checked=len(manifest),
        saved_probability_rows_checked=checked, steps_checked=len(training),
        temperature_combinations_checked=16,metric_tolerance=1e-12,
        all_metrics_family_kind_boundary_offset_and_paired_transitions_match=True,
        previous_v4_released_runtime_drift=drift,
        implementation='Python standard library only; does not import training runner or Jev metric implementations')
    (root / 'independent-replay.json').write_text(json.dumps(receipt, indent=2)+'\n')
    (root / 'exclusion-action-diagnostic.json').write_text(json.dumps(actions, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
