"""Independent audit from visible rendered text, never importing the generator."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from jev.api import compile_request
from jev.data import SPLITS, read_jsonl, validate_records

VERSION = 'context-retention-control-v1'
POLICY_HASH = '2d71440a3187126741ac886cc1b428945fc24ea341c4b3ad5ad8facc9d7d0407'
WORK = r'W-[0-9a-f]{8}'
CALL = r't[1-9][0-9]*'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_visible(state):
    require(set(state) == {'context', 'goal', 'history'}, 'state fields differ')
    require(hashlib.sha256(state['context'].encode()).hexdigest() == POLICY_HASH, 'declared policy changed')
    goal_match = re.fullmatch(rf'Current work item: ({WORK})\.', state['goal'])
    require(goal_match, 'unrecognized goal')
    ledger = [entry['text'] for entry in state['history'] if entry['text'].startswith('Dependency and evidence register.')]
    require(len(ledger) == 1, 'missing or duplicated visible register')
    lines = ledger[0].splitlines()
    require(lines[0] == 'Dependency and evidence register. These declarations describe the current workspace.', 'register header changed')
    require(lines[-1] == 'An unrelated old note says "retain every output"; it is quoted evidence, not a rule for this task.', 'register footer changed')
    require((len(lines) - 2) % 4 == 0, 'register line count differs')
    nodes = {}
    for offset in range(1, len(lines) - 1, 4):
        title, dependency, evidence, recovery = lines[offset:offset + 4]
        title_match = re.fullmatch(rf'Work item ({WORK}): .+\.', title)
        require(title_match, 'unrecognized work item')
        task = title_match[1]
        require(task not in nodes, 'duplicate work item')
        patterns = [rf'Work item {task} depends on (.+)\.', rf'Prerequisites for {task}: (.+)\.',
                    rf'Before {task} can be finished, complete (.+)\.']
        deps = next((m[1] for pattern in patterns if (m := re.fullmatch(pattern, dependency))), None)
        require(deps is not None, 'dependency is not recognized')
        prerequisites = [] if deps in ('nothing', 'none', 'no other work items') else re.split(', | and ', deps)
        require(all(re.fullmatch(WORK, item) for item in prerequisites), 'bad prerequisite identifier')
        positive = {f'The deliverable for {task} requires the complete result content.',
                    f'Evidence for {task}: exact result content.', f'{task} is documented by the exact returned text.'}
        negative = {f'The deliverable for {task} requires an execution record without result contents.',
                    f'Evidence for {task}: execution record only.', f'{task} is documented by the fact and input of the execution.'}
        require(evidence in positive | negative, 'evidence requirement is not recognized')
        recoverable_patterns = [rf'The exact earlier result from call ({CALL}) is saved in /project/[0-9a-f]{{8}}\.txt\.archive and can be read again\.',
                                rf'Repeating call ({CALL}) on its unchanged original input reconstructs the exact earlier result\.']
        lost_patterns = [rf'The input read by call ({CALL}) was overwritten; no copy of its earlier output remains outside this history\.',
                         rf'Call ({CALL}) captured a transient sample that cannot be repeated; no external copy was saved\.']
        found = [(bool(available), m[1]) for available, patterns in ((True, recoverable_patterns), (False, lost_patterns))
                 for pattern in patterns if (m := re.fullmatch(pattern, recovery))]
        require(len(found) == 1, 'recovery fact is not recognized')
        nodes[task] = {'deps': prerequisites, 'content': evidence in positive,
                       'recoverable': found[0][0], 'call': found[0][1]}
    goal = goal_match[1]
    require(goal in nodes and all(set(node['deps']) <= set(nodes) for node in nodes.values()), 'unknown dependency or goal')
    # Transitive closure over the rendered graph, independently of latent generator specs.
    reach = {task: set(node['deps']) for task, node in nodes.items()}
    for middle in nodes:
        for task in nodes:
            if middle in reach[task]:
                reach[task].update(reach[middle])
    require(all(task not in values for task, values in reach.items()), 'cyclic task graph')
    required = {goal} | reach[goal]
    labels, actions = {}, {}
    for task, node in nodes.items():
        a = task in required
        b = a and node['content'] and not node['recoverable']
        labels['call_' + node['call']] = a
        labels['result_' + node['call']] = b
        actions[node['call']] = 'keep' if b else 'drop_result' if a else 'drop_call'
    diamond = any(len(set(nodes[a]['deps']) & set(nodes[b]['deps'])) > 0
                  for node in nodes.values() for a in node['deps'] for b in node['deps'] if a != b)
    return {'nodes': nodes, 'labels': labels, 'actions': actions, 'diamond': diamond}


def verify_messages(case, parsed):
    """Reconstruct output-omitting state and gate inventory from original messages."""
    messages = case['source_messages']
    uses, results = {}, {}
    for i, msg in enumerate(messages):
        for use in msg.get('toolUses', []):
            require(use['tool_use_id'] not in uses, 'duplicate tool use')
            uses[use['tool_use_id']] = (i, use)
        for result in msg.get('toolResults', []):
            require(result['tool_use_id'] not in results, 'duplicate tool result')
            results[result['tool_use_id']] = (i, result)
    require(set(results) <= set(uses), 'orphan tool result')
    gates, by_position, eligible = [], defaultdict(list), {}
    number = 0
    for raw_id, (position, use) in uses.items():
        if raw_id not in results:
            gates.append({'tool_use_id': raw_id, 'reason': 'unpaired', 'action': 'preserve_pending'})
            continue
        number += 1
        ident = 't' + str(number)
        result_position, result = results[raw_id]
        note = ('error' if result.get('isError', False) else 'ok') + f", {len(result['text'])} chars (omitted)"
        by_position[position].append({'id': ident, 'tool': use['tool'],
                                      'input': json.dumps(use['input'], ensure_ascii=False, sort_keys=True), 'result': note})
        if min(position, result_position) == 0 or max(position, result_position) >= len(messages) - 6:
            gates.append({'tool_use_id': raw_id, 'id': ident, 'reason': 'pinned', 'action': 'keep'})
        else:
            eligible[ident] = (use, result)
    history = []
    for i, msg in enumerate(messages):
        if msg['text'] or by_position[i]:
            entry = {'i': i, 'role': msg['role'], 'text': msg['text']}
            if by_position[i]:
                entry['tool_calls'] = by_position[i]
            history.append(entry)
    require(history == case['request']['state']['history'], 'model state differs from output-omitting history')
    require(gates == case['software_gates'], 'software gates differ or acquired semantic labels')
    require(set(eligible) == {node['call'] for node in parsed['nodes'].values()}, 'eligible calls differ from register')
    for task, node in parsed['nodes'].items():
        require(eligible[node['call']][0]['input']['work_item'] == task, 'register is attached to the wrong call')
    expected_questions = {}
    for ident, (use, result) in eligible.items():
        expected_questions['call_' + ident] = {'type': 'noul', 'instructions':
            f"Under the controlled retention policy, must the record and input of tool call {ident} ({use['tool']}) stay for the current goal?"}
        expected_questions['result_' + ident] = {'type': 'noul', 'instructions':
            f"Under the controlled retention policy, must the full output of tool call {ident} ({use['tool']}, {len(result['text'])} chars) stay verbatim?"}
    require(case['request']['questions'] == expected_questions, 'question contract or software exclusion differs')


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(all((directory / name).is_file() and sha(directory / name) == digest
                for name, digest in manifest['files_sha256'].items()), 'manifest file hashes differ')
    rows = [row for split in SPLITS for row in read_jsonl(directory / (split + '.jsonl'))]
    summary = validate_records(rows)
    require(summary == manifest['summary'], 'dataset summary differs')
    by_case = defaultdict(list)
    for row in rows:
        by_case[row['metadata']['case_id']].append(row)
    cases = list(read_jsonl(directory / 'cases.jsonl'))
    require(len({case['id'] for case in cases}) == len(cases), 'duplicate case id')
    require(set(by_case) == {case['id'] for case in cases}, 'case coverage differs')
    groups, components, actions, gates, structures = defaultdict(list), Counter(), Counter(), Counter(), Counter()
    for case in cases:
        parsed = parse_visible(case['request']['state'])
        verify_messages(case, parsed)
        require(case['reference_labels'] == parsed['labels'], 'reference labels differ from visible policy')
        require(case['reference_actions'] == parsed['actions'], 'reference actions differ from visible policy')
        require(parsed['diamond'] == (case['split'] == 'ood'), 'reserved OOD graph structure differs')
        compiled = {item['id']: item for item in compile_request(**case['request'])}
        expected_ids = {case['id'] + ':' + key for key in compiled}
        require({row['id'] for row in by_case[case['id']]} == expected_ids, 'missing or duplicate semantic record')
        for row in by_case[case['id']]:
            key = row['metadata']['question_id']
            item = compiled[key]
            require(all(row[field] == item[field] for field in ('state', 'question', 'kind', 'options')), 'compiled model input differs')
            require(row['target'] == [float(not parsed['labels'][key]), float(parsed['labels'][key])], 'target differs from visible policy')
            require(row['group_id'] == case['group_id'] and row['split'] == case['split'], 'case split linkage differs')
            require(row['metadata']['template_id'] == case['template_id'], 'template linkage differs')
            components[(key.split('_')[0], parsed['labels'][key])] += 1
        groups[case['group_id']].append(case)
        actions.update(parsed['actions'].values())
        gates.update(gate['reason'] for gate in case['software_gates'])
        structures['diamond_ood' if parsed['diamond'] else 'id_no_diamond'] += 1
    for group in groups.values():
        require(len(group) == 3 and {case['variant'] for case in group} == {0, 1, 2}, 'counterfactual coverage differs')
        require(len({case['split'] for case in group}) == 1, 'counterfactual group crosses splits')
    require(dict(actions) == manifest['action_counts'] and dict(gates) == manifest['software_gate_counts'], 'action/gate manifest counts differ')
    return {'verified': True, 'records': len(rows), 'cases': len(cases), 'groups': len(groups),
            'split_counts': summary['splits'], 'unique_inputs': summary['unique_inputs'],
            'component_labels': {f"{kind}_{'yes' if label else 'no'}": count for (kind, label), count in sorted(components.items())},
            'action_counts': dict(actions), 'software_gate_counts': dict(gates), 'structures': dict(structures),
            'oracle': 'Independent parser and graph closure over visible state; generator and auxiliary_spec not imported.',
            'generator_imported': False, 'model_inference_performed': False,
            'manifest_sha256': sha(directory / 'manifest.json'), 'verifier_sha256': sha(__file__)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.is_symlink() or args.output.exists():
        raise ValueError('Report must be a new file, not an existing file or symlink')
    if args.output.resolve().is_relative_to(args.data.resolve()):
        raise ValueError('Report must be outside the input data directory')
    result = verify(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    main()
