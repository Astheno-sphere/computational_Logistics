"""Read-only independent mixture/panel audit; no generator or evaluator imports.

Inputs are versioned source datasets and the frozen mixture/panel only. The
output contains aggregate counts, source versions and digests, not utterances
or machine-specific paths. Benchmark questions/gold and model outputs are not
read. This does not run models or validate new model quality.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

SPLITS = ('train', 'calibration', 'validation', 'test', 'ood')
NEW_DIRECTORIES = ('data/community-routing-v3', 'data/sql-semantics-v3', 'data/community-workflow-v3')
OLD_DIRECTORY = 'data/community-hard-mix-v2-final'
EXPECTED_SOURCES = {'banking77-routing-v3', 'clinc150-routing-v3', 'sql-semantics-v3',
                    'community-workflow-v3/approval', 'community-workflow-v3/cms'}
OLD_MANIFEST = '7b26f948d2ae11f20d7a18be437d1ada616fc479e1596ae94be7596787fe4e54'
INPUT_FIELDS = ('state', 'question', 'kind', 'options')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open() as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def input_digest(row):
    return digest({**{key: row[key] for key in INPUT_FIELDS}, 'options': sorted(row['options'])})


def pinned_splits(directory, manifest):
    values = {split: file_hash(directory / (split + '.jsonl')) for split in SPLITS}
    assert manifest['files_sha256'] == {split + '.jsonl': value for split, value in values.items()}
    if 'sha256' in manifest:
        assert manifest['sha256'] == values
    return values


def replay_membership(groups_by_source, cap, seed):
    """Independently interleave fixed positions of hash-ordered source groups."""
    rank = lambda value: hashlib.sha256(f'{seed}:{value}'.encode()).hexdigest()
    kept = set()
    for source, groups in sorted(groups_by_source.items()):
        ordered = [sorted(groups[group], key=rank) for group in sorted(groups, key=rank)]
        source_ids = []
        for position in range(max(map(len, ordered))):
            source_ids.extend(group[position] for group in ordered if position < len(group))
            if len(source_ids) >= cap:
                break
        selected = source_ids[:cap]
        assert len(selected) == min(cap, sum(map(len, ordered)))
        kept.update(selected)
    return kept


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--mixture', type=Path, required=True)
    parser.add_argument('--panel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if sys.flags.optimize:
        raise ValueError('Do not disable audit assertions')
    assert not args.output.exists(), 'Audit output must be new'
    root, mixture, panel = args.repository, args.mixture, args.panel
    mixture_manifest, panel_manifest = read(mixture / 'manifest.json'), read(panel / 'manifest.json')
    mixture_manifest_sha, panel_manifest_sha = file_hash(mixture / 'manifest.json'), file_hash(panel / 'manifest.json')
    config = mixture_manifest['configuration']
    assert config['version'] == 'community-hard-mix-v3' and config['seed'] == 20260921
    assert config['replay_cap_per_source'] == 300 and config['excluded_groups'] == []
    bindings = {value['path']: value for value in config['input_bindings']}
    assert len(bindings) == len(config['input_bindings']) == 4
    assert set(bindings) == {*NEW_DIRECTORIES, OLD_DIRECTORY}
    assert bindings[OLD_DIRECTORY]['manifest_sha256'] == OLD_MANIFEST

    sources, source_manifests, source_pins = {}, {}, {}
    raw_group_splits, old_train_groups = defaultdict(set), defaultdict(lambda: defaultdict(list))
    new_ids, unchanged_heldout_ids = set(), set()
    forbidden_ids, forbidden_groups, forbidden_inputs = set(), set(), set()
    source_split_counts, old_train_counts = Counter(), Counter()
    new_candidate_max, old_candidate_max = 0, 0
    for directory_name in (*NEW_DIRECTORIES, OLD_DIRECTORY):
        directory = root / directory_name
        manifest = read(directory / 'manifest.json')
        binding = bindings[directory_name]
        category = 'new' if directory_name in NEW_DIRECTORIES else 'replay'
        assert binding['category'] == category
        assert file_hash(directory / 'manifest.json') == binding['manifest_sha256']
        actual_hashes = pinned_splits(directory, manifest)
        assert binding['files_sha256'] == actual_hashes
        version = manifest['configuration'].get('version', manifest['configuration'].get('generator_version'))
        source_manifests[version] = manifest
        source_pins[version] = {'manifest_sha256': binding['manifest_sha256'], 'files_sha256': actual_hashes, 'category': category}
        observed = Counter()
        for split in SPLITS:
            for row in rows(directory / (split + '.jsonl')):
                identifier = row['id']
                assert identifier not in sources and row['split'] == split
                assert row['source'] in EXPECTED_SOURCES if category == 'new' else row['source'] not in EXPECTED_SOURCES
                record_digest, visible_digest = digest(row), input_digest(row)
                sources[identifier] = (record_digest, split, category, row['source'], row['group_id'], visible_digest)
                raw_group_splits[row['group_id']].add(split)
                source_split_counts[category, split] += 1
                observed[split] += 1
                if split in ('train', 'calibration', 'validation'):
                    forbidden_ids.add(identifier)
                    forbidden_groups.add(row['group_id'])
                    forbidden_inputs.add(visible_digest)
                if category == 'new':
                    assert len(row['options']) <= 8
                    new_candidate_max = max(new_candidate_max, len(row['options']))
                    new_ids.add(identifier)
                else:
                    old_candidate_max = max(old_candidate_max, len(row['options']))
                    if split == 'train':
                        old_train_groups[row['source']][row['group_id']].append(identifier)
                        old_train_counts[row['source']] += 1
                    else:
                        unchanged_heldout_ids.add(identifier)
        assert dict(observed) == manifest['summary']['splits']
    assert all(len(splits) == 1 for splits in raw_group_splits.values())
    assert len({sources[identifier][3] for identifier in new_ids}) == 5
    selected_replay = replay_membership(old_train_groups, 300, config['seed'])
    expected_mixture = new_ids | unchanged_heldout_ids | selected_replay
    assert config['filtered'] == {'replay_train_cap': sum(old_train_counts.values()) - len(selected_replay)}

    mixture_hashes = pinned_splits(mixture, mixture_manifest)
    seen, mixture_groups = set(), defaultdict(set)
    observed_splits, observed_kinds, observed_sources = Counter(), Counter(), Counter()
    train_by_source, selected_replay_counts = Counter(), Counter()
    training_groups = defaultdict(set)
    new_train_rows, replay_train_rows, legacy_selected_candidate_max = 0, 0, 0
    for split in SPLITS:
        for row in rows(mixture / (split + '.jsonl')):
            identifier = row['id']
            assert identifier not in seen and row['split'] == split
            seen.add(identifier)
            assert identifier in expected_mixture
            reference = sources[identifier]
            assert digest(row) == reference[0] and split == reference[1], 'Mixture row changed from its source'
            mixture_groups[row['group_id']].add(split)
            observed_splits[split] += 1
            observed_kinds[row['kind']] += 1
            observed_sources[row['source']] += 1
            if split == 'train':
                train_by_source[row['source']] += 1
                training_groups[row['source']].add(row['group_id'])
                if reference[2] == 'new':
                    new_train_rows += 1
                else:
                    replay_train_rows += 1
                    selected_replay_counts[row['source']] += 1
                    legacy_selected_candidate_max = max(legacy_selected_candidate_max, len(row['options']))
    assert seen == expected_mixture
    assert all(len(splits) == 1 for splits in mixture_groups.values())
    assert dict(observed_splits) == mixture_manifest['summary']['splits'] == mixture_manifest['counts']
    assert dict(observed_kinds) == mixture_manifest['summary']['kinds']
    assert dict(observed_sources) == mixture_manifest['summary']['sources']
    assert len(seen) == mixture_manifest['summary']['records'] == 331249
    assert len(mixture_groups) == mixture_manifest['summary']['groups'] == 72210
    assert dict(train_by_source) == mixture_manifest['training_by_source']
    assert {source: len(groups) for source, groups in training_groups.items()} == mixture_manifest['training_groups_by_source']
    assert dict(selected_replay_counts) == {source: min(300, count) for source, count in old_train_counts.items()}
    assert new_train_rows == source_split_counts['new', 'train'] == 74921
    assert replay_train_rows == len(selected_replay) == 21928
    assert observed_splits['train'] == new_train_rows + replay_train_rows == 96849
    assert mixture_manifest['full_pass_four_gpu_steps'] == (96849 + 3) // 4 == 24213
    assert mixture_manifest['full_pass_four_gpu_rows_consumed'] == 96852
    assert mixture_manifest['full_pass_four_gpu_wrapped_rows'] == 3

    assert panel_manifest['version'] == 'community-pair-v1'
    assert panel_manifest['rows'] == 1280 and panel_manifest['per_source_split'] == 128
    assert panel_manifest['selection_precedes_inference'] is True
    assert panel_manifest['excluded_splits'] == ['train', 'calibration', 'validation']
    assert panel_manifest['model_input_fields'] == list(INPUT_FIELDS)
    assert file_hash(panel / 'panel.jsonl') == panel_manifest['panel_sha256']
    actual_panel_bindings = {binding['version']: binding for binding in panel_manifest['source_bindings']}
    assert len(actual_panel_bindings) == len(panel_manifest['source_bindings']) == 3
    assert set(actual_panel_bindings) == {source_manifests[version]['configuration'].get('version', source_manifests[version]['configuration'].get('generator_version'))
                                          for version, pin in source_pins.items() if pin['category'] == 'new'}
    for version, binding in actual_panel_bindings.items():
        assert binding['manifest_sha256'] == source_pins[version]['manifest_sha256']
        assert binding['files_sha256'] == {split + '.jsonl': value for split, value in source_pins[version]['files_sha256'].items()}
    panel_ids, panel_groups, panel_counts, panel_kind_counts = [], defaultdict(set), Counter(), Counter()
    for row in rows(panel / 'panel.jsonl'):
        identifier = row['id']
        assert identifier in new_ids and row['split'] in ('test', 'ood')
        reference = sources[identifier]
        assert digest(row) == reference[0], 'Panel row differs from its bound source'
        assert identifier not in forbidden_ids and row['group_id'] not in forbidden_groups and input_digest(row) not in forbidden_inputs
        assert identifier in seen and row['source'] in EXPECTED_SOURCES
        panel_ids.append(identifier)
        panel_groups[row['source'], row['split']].add(row['group_id'])
        panel_counts[row['source'], row['split']] += 1
        panel_kind_counts[row['source'], row['split'], row['kind']] += 1
    assert len(panel_ids) == len(set(panel_ids)) == 1280
    assert digest(panel_ids) == panel_manifest['ordered_ids_sha256']
    assert set(panel_counts) == {(source, split) for source in EXPECTED_SOURCES for split in ('test', 'ood')}
    assert set(panel_counts.values()) == {128}
    expected_panel_counts = [{'source': source, 'split': split, 'rows': count, 'unique_groups': len(panel_groups[source, split])}
                             for (source, split), count in sorted(panel_counts.items())]
    assert panel_manifest['counts'] == expected_panel_counts
    all_panel_groups = set().union(*panel_groups.values())
    assert len(all_panel_groups) == panel_manifest['unique_groups']
    assert 1280 - len(all_panel_groups) == panel_manifest['correlated_views_beyond_first_per_group']

    # Reconstruct the predeclared group-balanced panel independently from source
    # membership. This uses only IDs/group IDs and never reads target quality.
    expected_panel_ids = []
    seed = panel_manifest['seed']
    for source, split in sorted(panel_counts):
        grouped = defaultdict(list)
        for identifier in new_ids:
            reference = sources[identifier]
            if reference[3] == source and reference[1] == split:
                grouped[reference[4]].append(identifier)
        order = [sorted(grouped[group], key=lambda identifier: digest([seed, identifier]))
                 for group in sorted(grouped, key=lambda group: digest([seed, source, split, group]))]
        selected = []
        for position in range(max(map(len, order))):
            selected.extend(group[position] for group in order if position < len(group))
            if len(selected) >= 128:
                break
        expected_panel_ids.extend(selected[:128])
    assert expected_panel_ids == panel_ids

    # Confirm that no source, mixture or panel bytes changed during this audit.
    for directory_name, binding in bindings.items():
        assert file_hash(root / directory_name / 'manifest.json') == binding['manifest_sha256']
        assert pinned_splits(root / directory_name, read(root / directory_name / 'manifest.json')) == binding['files_sha256']
    assert file_hash(mixture / 'manifest.json') == mixture_manifest_sha
    assert pinned_splits(mixture, mixture_manifest) == mixture_hashes
    assert file_hash(panel / 'manifest.json') == panel_manifest_sha
    assert file_hash(panel / 'panel.jsonl') == panel_manifest['panel_sha256']

    workflow_audit_path = root / 'reports/community-workflow-v3/independent-audit.json'
    workflow_audit = read(workflow_audit_path) if workflow_audit_path.exists() else None
    workflow_pin = source_pins['community-workflow-v3']
    workflow_status = 'pending_independent_oracle_completion'
    workflow_hash = None
    if workflow_audit is not None and workflow_audit.get('manifest_sha256') == workflow_pin['manifest_sha256']:
        assert workflow_audit.get('target_mismatches') == 0 and workflow_audit.get('rows_audited') == 8280
        assert workflow_audit['files_sha256'] == {split + '.jsonl': value for split, value in workflow_pin['files_sha256'].items()}
        assert workflow_audit['generator_sha256'] == file_hash(root / 'jev/community_workflow_v3.py')
        assert workflow_audit['audit_script_sha256'] == file_hash(root / 'reports/community-workflow-v3/audit_visible_records.py')
        workflow_status = 'completed_audit_file_and_exact_source_hashes_verified'
        workflow_hash = file_hash(workflow_audit_path)
    report = {
        'schema_version': 1, 'status': 'passed', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Independent frozen-mixture and focus-panel integration audit; no benchmark questions/gold, model inference or quality results.',
        'audit_script_sha256': file_hash(Path(__file__)),
        'independence': 'No imports from generators, mixer or paired evaluator. Direct streaming source/mixture/panel comparison and independently reconstructed group-balanced selections.',
        'mixture_manifest_sha256': mixture_manifest_sha, 'mixture_split_sha256': mixture_hashes,
        'source_bindings': source_pins,
        'mixture_rows': len(seen), 'mixture_groups': len(mixture_groups), 'mixture_split_counts': dict(observed_splits),
        'training': {'new_rows': new_train_rows, 'replay_rows': replay_train_rows, 'total_rows': observed_splits['train'],
                     'replay_source_count': len(selected_replay_counts), 'replay_cap_per_source': 300,
                     'replay_available_rows': sum(old_train_counts.values()), 'replay_rows_excluded_by_cap': 126711,
                     'replay_selected_by_source': dict(sorted(selected_replay_counts.items())),
                     'new_training_rows_by_dataset': {version: source_manifests[version]['summary']['splits']['train']
                                                      for version, pin in source_pins.items() if pin['category'] == 'new'},
                     'full_pass_steps_four_ranks': 24213, 'full_pass_consumed_rows': 96852, 'wrapped_tail_rows': 3},
        'candidate_bounds': {'new_sources_max_options': new_candidate_max, 'all_legacy_source_max_options': old_candidate_max,
                             'selected_legacy_replay_train_max_options': legacy_selected_candidate_max,
                             'max_eight_requirement_applies_to_new_sources': True},
        'focus_panel': {'manifest_sha256': panel_manifest_sha, 'panel_sha256': panel_manifest['panel_sha256'],
                        'rows': 1280, 'sources': sorted(EXPECTED_SOURCES), 'source_count': 5,
                        'counts': expected_panel_counts, 'unique_groups': len(all_panel_groups),
                        'correlated_views_beyond_first_per_group': 1280 - len(all_panel_groups),
                        'kind_counts': [{'source': source, 'split': split, 'kind': kind, 'rows': count}
                                        for (source, split, kind), count in sorted(panel_kind_counts.items())],
                        'forbidden_overlap_checks': ['all new and old-v2 train/calibration/validation IDs',
                                                     'all new and old-v2 train/calibration/validation group IDs',
                                                     'canonical visible inputs ignoring candidate order'],
                        'overlapping_forbidden_rows': 0},
        'workflow_independent_oracle': {'status': workflow_status, 'audit_sha256': workflow_hash,
                                       'note': 'Checks audit binding/completion only; this integration script is not a second prose-label oracle.'},
        'checks': {key: True for key in [
            'source_manifests_match_all_mixture_input_bindings', 'source_split_hashes_match_all_five_files',
            'all_new_source_rows_retained_unchanged', 'all_old_nontraining_rows_retained_in_original_splits',
            'old_training_replay_exact_hash_group_round_robin_selection', 'global_300_per_old_training_source_cap',
            'training_96849_equals_all_new_74921_plus_replay_21928', 'no_duplicate_source_or_mixture_ids',
            'global_group_splits_disjoint', 'new_source_candidates_at_most_eight',
            'panel_exact_1280_from_five_new_sources_test_and_ood', 'panel_128_per_source_split',
            'panel_selection_replayed_without_targets_or_predictions', 'panel_rows_unchanged_from_bound_sources',
            'panel_disjoint_from_all_source_train_calibration_validation', 'panel_source_bindings_match_mixture_sources',
            'all_input_hashes_stable_before_and_after_audit']},
        'gpu_queries': 0, 'gpu_jobs': 0, 'provider_requests': 0, 'benchmark_gold_reads': 0,
        'limitations': ['Panel rows include correlated views; 1280 rows are not 1280 independent scenarios.',
                       'Integration integrity does not establish quality improvement.',
                       'Legacy replay can retain candidate catalogs larger than eight.',
                       'Natural routing remains two datasets; five panel source IDs are not five natural datasets.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')
    print(json.dumps({'status': 'passed', 'train_rows': observed_splits['train'], 'new_train_rows': new_train_rows,
                      'replay_train_rows': replay_train_rows, 'mixture_rows': len(seen), 'panel_rows': 1280,
                      'panel_unique_groups': len(all_panel_groups), 'workflow_oracle_status': workflow_status}, indent=2))


if __name__ == '__main__':
    main()
