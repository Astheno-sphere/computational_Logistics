"""One declared comparison-only supplement; preserve the consumed v7 attempt."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
from types import SimpleNamespace

from scripts.run_boundary_training_v7 import RUNTIME_NAMES, SOURCE_COMMIT, file_inventory, require, sha, validate_resource

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = ROOT/'reports/boundary-v7-forensic-comparison-20261003/declaration.json'
KIND = 'v7_comparison_only_supplement'
SUPPLEMENT_ID = 'boundary-v7-comparison-s2-20261003'
ORIGINAL_EVALUATION = '37729b2340e8d00fb211784d2181dd167db4f96b'
RESTORED = 'verified_optimizer_sampler_tree_four_ranks_and_real_completions'


def same_json(left, right):
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def write_once(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def validate_supplement(args, receipt, original_request, output):
    """CPU provenance check, before any inference; never rewrites old evidence."""
    path = Path(args.supplemental_request).resolve()
    request = json.loads(path.read_text())
    declaration = json.loads(DECLARATION.read_text())
    origin = declaration['origin']
    require(type(request.get('schema_version')) is int and type(declaration.get('schema_version')) is int
            and request.get('schema_version') == declaration.get('schema_version') == 1
            and request.get('kind') == declaration.get('kind') == KIND
            and request.get('supplement_id') == declaration.get('supplement_id') == SUPPLEMENT_ID
            and declaration['status'] == 'declared_not_executed'
            and type(declaration['training_calls']) is int and declaration['training_calls'] == 0
            and declaration['automatic_retry'] is False and declaration['automatic_promotion'] is False,
            'Unknown comparison-only declaration/request')
    require(request['declaration_sha256'] == sha(DECLARATION)
            and request['evaluation_commit'] == args.expected_commit
            and origin['evaluation_commit'] == original_request['evaluation_commit'] == ORIGINAL_EVALUATION,
            'Supplement source/declaration/original evaluation differs')
    require(declaration['training_source_commit'] == receipt['source_commit'] == SOURCE_COMMIT
            and declaration['plan_sha256'] == original_request['plan_sha256']
            and declaration['completed_checkpoint_directory_sha256'] == receipt['checkpoint']['directory_sha256']
            and declaration['physical_gpu_uuid'] == receipt['gpu_uuid'],
            'Declared frozen training/plan/checkpoint/hardware differs')
    for key in ('dataset', 'released_checkpoint', 'training_run', 'completion_receipt'):
        require(Path(request[key]).resolve() == Path(original_request[key]).resolve()
                == Path(getattr(args, key)).resolve(), 'Supplement changed completed input: '+key)
    require(request['plan_sha256'] == original_request['plan_sha256']
            and request['gpu_uuid'] == receipt['gpu_uuid'] == original_request['gpu_uuid']
            and request['runtime'] == original_request['runtime'],
            'Supplement changed the frozen plan/hardware/runtime')
    task = Path(args.completion_receipt).resolve().parent
    require(Path(request['original_task']).resolve() == task
            and Path(receipt['execution_request_path']).resolve() == task/'execution-request.json',
            'Supplement origin task differs')
    require(path.name == 'comparison-supplement-request.json'
            and Path(request['comparison_output']).resolve() == Path(output).resolve() == path.parent/'comparison'
            and Path(request['resource_receipt']).resolve() == path.parent/'resource-ready.json'
            and Path(request['controller_plan']).resolve() == path.parent/'controller-plan.json',
            'Supplement outputs/resources must use its new task root')
    require(ROOT.is_dir() and ROOT == ROOT.resolve() == path.parent/'evaluation-source',
            'Supplement source must be its canonical evaluation-source directory')
    for old in (task, Path(args.dataset).resolve(), Path(args.released_checkpoint).resolve()):
        require(not path.parent.is_relative_to(old) and not old.is_relative_to(path.parent),
                'Supplement task overlaps original evidence or inputs')
    for key in ('original_task', 'original_controller_receipt', 'original_restoration_audit',
                'dataset', 'released_checkpoint', 'training_run', 'completion_receipt',
                'comparison_output', 'resource_receipt', 'controller_plan'):
        require(Path(request[key]).is_absolute() and 'future-host' not in Path(request[key]).parts,
                'Supplement requires actual absolute paths: '+key)
    original_comparison = Path(original_request['comparison_output'])
    require(original_comparison.resolve() == task/'comparison'
            and file_inventory(original_comparison) == origin['failed_comparison_files_sha256']
            and set(origin['failed_comparison_files_sha256']) == {'comparison.lock.json'},
            'Original failed comparison inventory changed or contains predictions')
    files = {str(path): sha(path), str(DECLARATION): sha(DECLARATION)}
    for filename, key in (('execution-request.json', 'execution_request_sha256'),
                          ('completion-receipt.json', 'completion_receipt_sha256'),
                          ('experiment-completion.json', 'experiment_completion_sha256'),
                          ('comparison.log', 'failure_log_sha256')):
        original = task/filename
        require(sha(original) == origin[key], 'Original failure/completion bytes changed: '+filename)
        files[str(original)] = origin[key]
    files.update({str(original_comparison/name): digest for name, digest in origin['failed_comparison_files_sha256'].items()})
    failure = json.loads((task/'experiment-completion.json').read_text())
    require(failure['training_status'] == 'complete' and type(failure['comparison_returncode']) is int
            and failure['comparison_returncode'] == 1 and failure['automatic_promotion'] is False
            and failure['training_completion_receipt_sha256'] == origin['completion_receipt_sha256']
            and failure['execution_request_sha256'] == origin['execution_request_sha256'],
            'Origin must be the completed training with failed comparison')
    require('ValueError: Published/final comparison runtime or recorded training packages differ'
            in (task/'comparison.log').read_text(), 'Original failure diagnostic differs')
    controller_path, audit_path = map(Path, (request['original_controller_receipt'], request['original_restoration_audit']))
    require(sha(controller_path) == origin['controller_final_sha256']
            and sha(audit_path) == origin['restoration_audit_sha256'], 'Original full restoration proof changed')
    controller, audit = json.loads(controller_path.read_text()), json.loads(audit_path.read_text())
    require(controller['status'] == audit['controller_status'] == 'v7_failed_original_queue_verified'
            and controller['queue_restoration'] == audit['queue_restoration'] == RESTORED
            and controller['evaluation_commit'] == audit['evaluation_commit'] == ORIGINAL_EVALUATION
            and controller['source_commit'] == audit['source_commit'] == SOURCE_COMMIT
            and controller_path.name == Path(audit['controller_receipt']).name,
            'Original terminal recovery identity differs')
    require(audit['status'] == 'independently_verified_original_queue_restored_owned_controller_guard_driver_gone'
            and audit['restoration_evidence_complete'] is True and audit['full_hashes'] is True
            and audit['failed_checks'] == [] and audit['checks']
            and all(v is True for v in audit['checks'].values())
            and all(audit[name+'_current_identity'] is None for name in ('controller', 'guard', 'driver')),
            'Original complete independent recovery required')
    files.update({str(controller_path): sha(controller_path), str(audit_path): sha(audit_path)})
    return dict(request=request, request_path=str(path), request_sha256=sha(path),
                declaration_sha256=sha(DECLARATION), files_sha256=files,
                original_evaluation_commit=ORIGINAL_EVALUATION,
                original_comparison_output=str(original_comparison), training_calls=0)


def comparison_args(args, request):
    return SimpleNamespace(**{key: request[key] for key in
        ('dataset', 'released_checkpoint', 'training_run', 'completion_receipt')},
        output=request['comparison_output'], expected_commit=args.expected_commit,
        plan=str(ROOT/'reports/boundary-controls-v7-20261002/prepared-training/comparison-plan.json'),
        device='cuda:0', supplemental_request=str(Path(args.request).resolve()))


def prepare(args):
    from scripts.compare_boundary_training_v7 import prepare as prepare_comparison
    request = json.loads(Path(args.request).read_text())
    compared = comparison_args(args, request)
    _, rows, _, _, inputs = prepare_comparison(compared)
    require(set(request['runtime']) == set(RUNTIME_NAMES)
            and {name: version(name) for name in RUNTIME_NAMES} == request['runtime'],
            'Supplement interpreter packages differ from original runtime')
    preflight = preflight_record(args.request, rows, inputs)
    return request, compared, preflight


def preflight_record(request_path, rows, inputs):
    request = inputs['supplemental_provenance']['request']
    return dict(status='comparison_only_cpu_preflight_passed_no_model_load',
        supplement_id=SUPPLEMENT_ID, training_calls=0, evaluation_source=inputs['evaluation_source'],
        request_sha256=sha(request_path), declaration_sha256=sha(DECLARATION),
        completed_training_receipt_sha256=sha(request['completion_receipt']),
        comparison_counts={name: len(values) for name, values in rows.items()},
        inputs_sha256=inputs['files_sha256'], checkpoint_directory_sha256=inputs['checkpoint_directory_sha256'])


def verify_controller_parent(identity, boot, command, directory):
    require(type(identity['pid']) is int and identity['pid'] == os.getppid()
            and identity['boot_id'] == boot and type(identity['start_ticks']) is int
            and type(identity['uid']) is int and identity['uid'] == os.getuid(),
            'Supplement controller parent identity differs')
    process = Path('/proc')/str(identity['pid'])
    fields = (process/'stat').read_text().rsplit(')', 1)[1].split()
    require(process.stat().st_uid == identity['uid'] and int(fields[19]) == identity['start_ticks']
            and fields[0] not in ('Z', 'X', 'T', 't'), 'Supplement controller is stale or not live')
    require((process/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0') == command
            and (process/'cwd').resolve() == Path(directory).resolve(),
            'Live parent is not the reviewed supplemental controller command/cwd')
    after = (process/'stat').read_text().rsplit(')', 1)[1].split()
    require(int(after[19]) == identity['start_ticks'] and process.stat().st_uid == identity['uid']
            and after[0] not in ('Z', 'X', 'T', 't'), 'Supplement controller changed during command verification')


def verify_restoration_guard(guard, controller, boot):
    require(type(guard['pid']) is int and guard['pid'] > 0
            and guard['pid'] not in (controller['pid'], os.getpid())
            and type(guard['start_ticks']) is int and guard['start_ticks'] > 0
            and type(guard['uid']) is int and guard['uid'] == controller['uid'] == os.getuid()
            and guard['boot_id'] == controller['boot_id'] == boot,
            'Supplement requires a distinct restoration guard identity')
    process = Path('/proc')/str(guard['pid'])
    fields = (process/'stat').read_text().rsplit(')', 1)[1].split()
    require(int(fields[1]) == controller['pid'] and int(fields[19]) == guard['start_ticks']
            and process.stat().st_uid == guard['uid'] and fields[0] not in ('Z', 'X', 'T', 't'),
            'Restoration guard child/birth/UID/live identity changed')


def validate_launch(args, provenance, rows, inputs):
    """Required by comparator too, so its supplemental CLI cannot bypass the guard."""
    path = Path(provenance['request_path'])
    request = provenance['request']
    preflight_path = path.parent/'comparison-supplement-preflight.json'
    require(same_json(json.loads(preflight_path.read_text()), preflight_record(path, rows, inputs)),
            'Supplement requires the exact current CPU preflight')
    require(set(request['runtime']) == set(RUNTIME_NAMES)
            and {name: version(name) for name in RUNTIME_NAMES} == request['runtime'],
            'Supplement interpreter packages differ from original runtime')
    lock = json.loads((path.parent/'attempt.lock.json').read_text())
    plan_path = Path(request['controller_plan']); plan = json.loads(plan_path.read_text())
    controller_path = path.parent/'pause_v7_comparison_restore.py'
    expected_controller = ['/usr/bin/python3', str(controller_path), '--execute']
    require(type(plan['schema_version']) is int and plan['schema_version'] == 1
            and plan['kind'] == KIND and plan['supplement_id'] == SUPPLEMENT_ID
            and plan['evaluation_commit'] == args.expected_commit and plan['source_commit'] == SOURCE_COMMIT
            and plan['gpu_uuid'] == request['gpu_uuid'] and plan['controller_sha256'] == sha(controller_path)
            and plan['driver_sha256'] == sha(__file__) and plan['execution_request_sha256'] == sha(path)
            and plan['cpu_preflight_receipt_sha256'] == sha(preflight_path)
            and plan['declaration_sha256'] == provenance['declaration_sha256']
            and plan['controller_command'] == expected_controller
            and Path(plan['controller_working_directory']).resolve() == path.parent,
            'Supplement controller plan/source/preflight binding differs')
    require(lock['status'] == 'single_comparison_supplement_started_no_retry'
            and lock['request_sha256'] == provenance['request_sha256']
            and lock['runner_sha256'] == sha(__file__) and lock['evaluation_commit'] == args.expected_commit
            and type(lock['pid']) is int and lock['pid'] == os.getpid() == os.getsid(0)
            and lock['preflight_receipt_sha256'] == sha(preflight_path)
            and lock['controller_plan_sha256'] == sha(plan_path)
            and lock['resource_receipt_sha256'] == sha(request['resource_receipt']),
            'Supplement requires its newly locked controller-owned session')
    raw_resource = json.loads(Path(request['resource_receipt']).read_text())
    require(raw_resource['restoration_required'] is True and raw_resource['kind'] == KIND
            and raw_resource['supplement_id'] == SUPPLEMENT_ID
            and raw_resource['source_commit'] == SOURCE_COMMIT and raw_resource['evaluation_commit'] == args.expected_commit
            and raw_resource['driver_sha256'] == sha(__file__) and raw_resource['execution_request_sha256'] == sha(path)
            and raw_resource['controller_plan_sha256'] == sha(plan_path)
            and raw_resource['declaration_sha256'] == provenance['declaration_sha256']
            and same_json(raw_resource['controller_identity'], lock['controller_identity']),
            'Supplement resource does not belong to this guarded acquisition')
    verify_controller_parent(raw_resource['controller_identity'], raw_resource['boot_id'],
                             expected_controller, str(path.parent))
    verify_restoration_guard(raw_resource['restoration_guard_identity'], raw_resource['controller_identity'], raw_resource['boot_id'])
    started, checked = datetime.fromisoformat(lock['started_at_utc']), datetime.fromisoformat(raw_resource['checked_at_utc'])
    require(started.tzinfo is not None and checked.tzinfo is not None
            and 0 <= (started-checked).total_seconds() <= 120,
            'Supplement lock does not record a fresh resource acquisition')
    resource = validate_resource(request)
    verify_controller_parent(raw_resource['controller_identity'], raw_resource['boot_id'],
                             expected_controller, str(path.parent))
    verify_restoration_guard(raw_resource['restoration_guard_identity'], raw_resource['controller_identity'], raw_resource['boot_id'])
    verified = datetime.now(timezone.utc)
    require(checked <= started <= verified and 0 <= (verified-checked).total_seconds() <= 120,
            'Supplement ownership/resource became stale during GPU queries')
    return dict(resource=resource, resource_receipt_sha256=sha(request['resource_receipt']),
                controller_plan_sha256=sha(plan_path), preflight_receipt_sha256=sha(preflight_path),
                launch_verified_at_utc=verified.isoformat())


def execute(args):
    from scripts.compare_boundary_training_v7 import run as compare
    request, compared, preflight = prepare(args)
    task = Path(args.request).resolve().parent
    if args.preflight_only:
        write_once(task/'comparison-supplement-preflight.json', preflight)
        return preflight
    require(same_json(json.loads((task/'comparison-supplement-preflight.json').read_text()), preflight),
            'Supplement CPU preflight/source/input binding changed')
    require(os.getpid() == os.getsid(0), 'Supplement must lead a new controller-owned session')
    write_once(task/'attempt.lock.json', dict(status='single_comparison_supplement_started_no_retry',
        request_sha256=sha(args.request), evaluation_commit=args.expected_commit,
        runner_sha256=sha(__file__), pid=os.getpid(), training_calls=0,
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        preflight_receipt_sha256=sha(task/'comparison-supplement-preflight.json'),
        controller_plan_sha256=sha(request['controller_plan']),
        resource_receipt_sha256=sha(request['resource_receipt']),
        controller_identity=json.loads(Path(request['resource_receipt']).read_text())['controller_identity']))
    try:
        compare(compared)
    except BaseException as error:
        write_once(task/'comparison-supplement-failure.json', dict(error_type=type(error).__name__,
            error=str(error), training_calls=0, automatic_retry=False, automatic_promotion=False))
        raise
    write_once(task/'comparison-supplement-completion.json', dict(status='comparison_only_complete',
        training_calls=0, request_sha256=sha(args.request), completed_training_receipt_sha256=sha(request['completion_receipt']),
        summary_sha256=sha(task/'comparison/summary.json'), automatic_promotion=False))
    return dict(status='comparison_only_complete', training_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--preflight-only', action='store_true')
    result = execute(parser.parse_args())
    print(json.dumps({key:result[key] for key in ('status','training_calls')}), flush=True)


if __name__ == '__main__':
    main()
