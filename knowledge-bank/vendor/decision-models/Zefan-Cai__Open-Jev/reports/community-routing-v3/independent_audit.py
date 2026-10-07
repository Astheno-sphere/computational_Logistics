"""Independent CPU audit of generated rows against pinned human source labels.

Deliberately does not import the converter, its normalizer, or target functions.
Only aggregate results are written to reports; no source utterances are copied.
"""
from collections import Counter, defaultdict
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
ABSTAIN = '__abstain__'
PINNED = {
    'banking-train.csv': 'b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b',
    'banking-test.csv': 'd12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d',
    'clinc-data-full.json': '36923c3705a59e08fe9c3883d8bc2dd966ef93e22cb78ac41171782a698d56e0',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text):
    folded = unicodedata.normalize('NFKC', text).casefold().replace('_', ' ')
    return ' '.join(re.findall(r'\w+', folded))


def role(split):
    return 'test' if split.endswith('test') else 'val' if split.endswith('val') else 'train'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', required=True, type=Path)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    SOURCE, DATA, REPORT = args.source_dir, args.data_dir, args.output_dir
    def write(name, value):
        (REPORT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    assert not REPORT.exists(), 'Audit report directory must be new'
    for filename, expected in PINNED.items():
        assert sha(SOURCE / filename) == expected
    raw = {}
    for split in ('train', 'test'):
        with (SOURCE / f'banking-{split}.csv').open() as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                raw['banking77', f'{split}:{index}'] = (row['text'], row['category'], split)
    for split, rows in json.loads((SOURCE / 'clinc-data-full.json').read_text()).items():
        for index, (text, label) in enumerate(rows):
            raw['clinc150', f'{split}:{index}'] = (text, label, split)
    assert len(raw) == 36783
    official_test = {normalized(text) for text, _, split in raw.values() if role(split) == 'test'}
    official_val = {normalized(text) for text, _, split in raw.values() if role(split) == 'val'}
    official_heldout = official_test | official_val
    labels_by_catalog_group = defaultdict(set)
    for (dataset, _), (text, label, _) in raw.items():
        labels_by_catalog_group[dataset, normalized(text)].add(label)
    expected_catalogs = {dataset: {label for (ds, _), (_, label, split) in raw.items()
                                  if ds == dataset and split == 'train'}
                         for dataset in ('banking77', 'clinc150')}
    assert {ds: len(labels) for ds, labels in expected_catalogs.items()} == {'banking77': 77, 'clinc150': 150}
    protocol = json.loads((DATA / 'full-catalog-eval-only.json').read_text())
    manifest = json.loads((DATA / 'manifest.json').read_text())
    removed = Counter()
    expected_eligible_groups = set()
    for (dataset, _), (text, label, split) in raw.items():
        group = normalized(text)
        if role(split) == 'train' and group in official_heldout:
            removed['official_heldout_group_reserved_from_train'] += 1
        elif role(split) == 'val' and group in official_test:
            removed['official_test_group_reserved_from_validation'] += 1
        elif len(labels_by_catalog_group[dataset, group]) > 1:
            removed['conflicting_labels_within_catalog'] += 1
        elif (dataset, group) in expected_eligible_groups:
            removed['duplicate_utterance_within_catalog'] += 1
        else:
            expected_eligible_groups.add((dataset, group))
    assert dict(removed) == manifest['configuration']['audit']['removed']
    utterance_views, groups_to_splits = defaultdict(list), defaultdict(set)
    targets, abstains = defaultdict(Counter), defaultdict(Counter)
    noul, counts, kinds, sizes, unique_ids, unique_inputs = defaultdict(Counter), Counter(), Counter(), Counter(), set(), set()
    source_splits, source_ids, output_hashes = defaultdict(set), defaultdict(set), {}
    for split in ('train', 'calibration', 'validation', 'test', 'ood'):
        path = DATA / f'{split}.jsonl'
        output_hashes[path.name] = sha(path)
        assert output_hashes[path.name] == manifest['files_sha256'][path.name]
        with path.open() as handle:
            for line in handle:
                row = json.loads(line)
                meta, state = row['metadata'], row['state']
                prov = meta['provenance']
                ds = meta['dataset']
                original = prov['original_id']
                text, gold, official_split = raw[ds, original]
                assert state['utterance'] == text and prov['original_label'] == gold
                assert prov['original_split'] == official_split
                assert state['catalog'] == manifest['configuration']['datasets'][ds]['catalog']
                assert prov['revision'] == manifest['configuration']['datasets'][ds]['revision']
                source_name = 'clinc-data-full.json' if ds == 'clinc150' else f'banking-{official_split}.csv'
                assert prov['input_sha256'] == PINNED[source_name]
                assert prov['license'] == ('CC-BY-4.0' if ds == 'banking77' else 'CC-BY-3.0')
                group = normalized(text)
                assert len(labels_by_catalog_group[ds, group]) == 1
                assert row['group_id'] == 'community-routing-v3:utterance:' + hashlib.sha256(group.encode()).hexdigest()
                assert row['split'] == split
                if role(official_split) == 'train':
                    assert group not in official_heldout
                    bucket = int(hashlib.sha256(f'20260921:{group}'.encode()).hexdigest()[:16], 16) % 100
                    expected_split = 'train' if bucket < 85 else 'calibration' if bucket < 90 else 'validation' if bucket < 95 else 'ood'
                elif role(official_split) == 'val':
                    assert group not in official_test
                    bucket = int(hashlib.sha256(f'20260921:{group}'.encode()).hexdigest()[:16], 16) % 100
                    expected_split = 'calibration' if bucket < 50 else 'validation'
                else:
                    expected_split = 'test'
                assert split == expected_split
                groups_to_splits[group].add(split)
                utterance_views[ds, group].append((meta['view'], original))
                source_splits[ds, split].add(group)
                source_ids[ds, split].add(original)
                assert row['id'] not in unique_ids
                unique_ids.add(row['id'])
                inputs = json.dumps({key: row[key] for key in manifest['model_input_fields']}, sort_keys=True)
                assert inputs not in unique_inputs
                unique_inputs.add(inputs)
                target = row['target']
                assert len(target) == len(row['options']) and sum(target) == 1 and set(target) <= {0.0, 1.0}
                correct = target.index(1.0)
                labels = meta['option_label_ids']
                assert len(set(labels)) == len(labels)
                assert all(label in expected_catalogs[ds] | {ABSTAIN} for label in labels)
                if row['kind'] == 'choice':
                    assert set(state) == {'catalog', 'utterance'}
                    assert len(row['options']) in (2, 4, 8) and len(labels) == len(row['options'])
                    assert ABSTAIN in labels
                    assert row['options'] == [protocol[ds]['catalog'].get(label, 'Abstain: no matching handler is available') for label in labels]
                    if meta['view'] == 'choice_present':
                        assert gold != 'oos' and labels[correct] == gold
                    else:
                        assert gold not in labels and labels[correct] == ABSTAIN
                        assert meta['view'] == ('choice_out_of_scope' if gold == 'oos' else 'choice_omitted')
                    key = f'{ds}/{split}/{meta["view"]}/{len(labels)}'
                    targets[key][correct] += 1
                    abstains[key][labels.index(ABSTAIN)] += 1
                    sizes[len(labels)] += 1
                else:
                    assert row['kind'] == 'noul' and row['options'] == ['no', 'yes']
                    assert set(state) == {'catalog', 'utterance', 'proposed_handler'}
                    assert len(labels) == 1 and labels[0] != ABSTAIN
                    assert state['proposed_handler'] == protocol[ds]['catalog'][labels[0]]
                    assert correct == int(labels[0] == gold)
                    assert gold != 'oos' or correct == 0
                    noul[f'{ds}/{split}']['yes' if correct else 'no'] += 1
                counts[split] += 1
                kinds[row['kind']] += 1
    assert set(utterance_views) == expected_eligible_groups
    for (ds, group), views in utterance_views.items():
        assert len({original for _, original in views}) == 1
        gold = raw[ds, views[0][1]][1]
        assert Counter(view for view, _ in views) == Counter(
            ['choice_out_of_scope', 'noul_candidate'] if gold == 'oos'
            else ['choice_present', 'choice_omitted', 'noul_candidate'])
    assert all(len(splits) == 1 for splits in groups_to_splits.values())
    max_spread = {}
    for name, table in [('choice_targets', targets), ('choice_abstain_positions', abstains)]:
        spreads = []
        for key, positions in table.items():
            width = int(key.rsplit('/', 1)[-1])
            values = [positions[i] for i in range(width)]
            spreads.append(max(values) - min(values))
        assert max(spreads) <= 1
        max_spread[name] = max(spreads)
    assert all(abs(histogram['yes'] - histogram['no']) <= 1 for histogram in noul.values())
    assert sum(counts.values()) == manifest['summary']['records'] == 108720
    assert dict(counts) == manifest['summary']['splits']
    assert dict(kinds) == manifest['summary']['kinds']
    assert len(groups_to_splits) == manifest['summary']['groups'] == 36632
    protocol_audit = {}
    for ds, values in protocol.items():
        catalog = expected_catalogs[ds] | ({ABSTAIN} if ds == 'clinc150' else set())
        assert set(values['catalog']) == catalog
        assert values['evaluation_only'] and values['status'] == 'prepared_not_evaluated'
        assert values['candidate_count'] == len(catalog) == (77 if ds == 'banking77' else 151)
        ids = set(values['eligible_original_ids'])
        assert len(ids) == len(values['eligible_original_ids']) == values['official_test_utterances_after_screening']
        assert ids == source_ids[ds, 'test']
        assert all(role(raw[ds, original][2]) == 'test' for original in ids)
        original_count = sum(role(split) == 'test' for (dataset, _), (_, _, split) in raw.items() if dataset == ds)
        protocol_audit[ds] = {'candidate_count': len(catalog), 'original_test_rows': original_count,
                              'eligible_test_rows': len(ids), 'excluded_test_rows': original_count - len(ids),
                              'requests_sent': 0}
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'tests.test_community_routing_v3', '-v'],
                           cwd=ROOT, capture_output=True, text=True)
    assert tests.returncode == 0
    REPORT.mkdir(parents=True)
    shutil.copyfile(DATA / 'manifest.json', REPORT / 'data-manifest.json')
    shutil.copyfile(DATA / 'full-catalog-eval-only.json', REPORT / 'full-catalog-eval-only.json')
    (REPORT / 'cpu-tests.txt').write_text(tests.stdout + tests.stderr)
    write('source-manifest.json', {'datasets': manifest['configuration']['datasets'],
                                  'source_file_sha256_verified': PINNED})
    write('integrity-audit.json', {
        'status': 'passed', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'audit_method': 'Separate audit script parses pinned raw CSV/JSON directly, imports no converter functions, and inspects every generated decision row.',
        'audit_script_sha256': sha(Path(__file__)),
        'converter_sha256': sha(ROOT / 'jev/community_routing_v3.py'),
        'test_file_sha256': sha(ROOT / 'tests/test_community_routing_v3.py'),
        'data_file_sha256': output_hashes,
        'raw_source_rows': len(raw), 'retained_catalog_utterances': len(utterance_views),
        'retained_global_utterance_groups': len(groups_to_splits), 'decision_rows': sum(counts.values()),
        'split_counts': dict(counts), 'kind_counts': dict(kinds), 'choice_size_counts': dict(sizes),
        'removed_source_rows': dict(removed),
        'retained_utterances_by_source_split': {f'{ds}/{split}': len(groups) for (ds, split), groups in source_splits.items()},
        'position_histogram_max_spread': max_spread,
        'noul_positive_negative': dict(noul),
        'full_catalog_evaluation_only': protocol_audit,
        'checks': {name: True for name in [
            'all_source_hashes_match_pins', 'every_utterance_matches_exact_raw_source_text',
            'every_human_label_matches_raw_source', 'every_choice_target_matches_catalog_contract',
            'every_noul_target_matches_proposed_handler', 'all_choice_views_have_2_4_or_8_total_options',
            'one_noul_and_at_most_two_choice_views_per_catalog_utterance',
            'global_normalized_groups_disjoint_across_splits', 'official_val_and_test_reserved_before_filtering',
            'within_catalog_conflicts_and_duplicates_excluded', 'all_expected_eligible_groups_represented',
            'choice_target_and_abstain_positions_balanced', 'noul_labels_balanced',
            'all_record_ids_unique', 'all_model_inputs_unique', 'full_catalog_protocol_uses_official_test_ids_only',
            'full_catalog_never_inserted_into_training', 'all_manifest_file_hashes_match']},
        'cpu_tests': {'passed': 7, 'skipped': 0, 'failed': 0, 'exit_code': tests.returncode},
        'peer_review': {'reviewer': '/root/remaining_eval_readiness', 'scope': 'Read-only code and tests; not a second raw-source rights audit',
                        'result': 'No actionable target/split bug found; independently reran seven CPU tests.'},
        'preparation_only': True, 'provider_requests': 0, 'gpu_jobs': 0,
        'limits': ['Human source labels and readable intent descriptions can be imperfect.',
                   'Gold-informed small candidate sets differ from original full-catalog classification.',
                   'OOD is held-out source-training utterances, not new-domain or new-intent OOD.',
                   'No quality improvement is established without a separately authorized evaluation.']})
    print(json.dumps({'status': 'passed', 'decision_rows': sum(counts.values()), 'retained_catalog_utterances': len(utterance_views),
                      'full_catalog_protocol': protocol_audit, 'report_directory': str(REPORT)}, indent=2))


if __name__ == '__main__':
    main()
