"""CPU preparation of the scientific child; production execution is unavailable.

The new episode caller owns attempt consumption, live lease proof, worker
identity and original-queue restoration. This module never substitutes a JSON
flag or CPU fixture owner for that proof. It creates no declaration or freeze.
Production module loading and the CLI refuse before reading paths or importing
Torch. The separately named fixture pipeline tests the proposed orchestration
using injected CPU callables, including the unchanged comparator arithmetic.
"""
import argparse
from contextlib import AbstractContextManager
from dataclasses import dataclass
import math
from pathlib import PurePosixPath
import re
from types import SimpleNamespace


SCIENCE_A = 'd8eeb3d1f8e8d8751476f102ab456170c277e86a'
NATIVE_A = '4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2'
PLAN_SHA = '984539a92f1aa37b93e58fea7df4511a1635e7e9f284531068bb5a0939ebc8be'
FREEZE_SHA = 'a710f79977ac582cdc9269368e3f442abb88e76e4bbfae89b962116ade213a5f'
FIXTURE_SCOPE = 'injected_CPU_fixture_no_model_or_resource_authority'


class ScientificChildUnavailable(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_production_modules(*args, **kwargs):
    raise ScientificChildUnavailable('Production scientific child unavailable: current runtime, '
        'optimizer-boundary, operational-source and live GPU/restoration authority are not closed')


def execute_child(*args, **kwargs):
    """No owner token, receipt or path can unlock this preparation entrypoint."""
    raise ScientificChildUnavailable('Production scientific child execution unavailable; '
                                     'a separately reviewed live episode is still required')


@dataclass(frozen=True)
class CPUFixtureModules:
    """Injected test code, not an installed scientific/native module bundle."""
    verify_sources: object
    driver: object
    trainer: object
    native: object
    comparator: object
    read_comparison_inputs: object
    write_json: object
    sha: object
    scope: str = FIXTURE_SCOPE


def _path(value):
    require(isinstance(value, str) and value and '\0' not in value, 'Actual lexical path required')
    path = PurePosixPath(value)
    require(path.is_absolute() and '..' not in path.parts and path.as_posix() == value,
            'Normalized absolute lexical path required')
    return path


def check_prepared_layout(context):
    """Lexical checks only; a future source verifier must inspect actual files."""
    roots = [_path(context[name]) for name in ('scientific_root', 'native_root', 'operational_root')]
    require(all(not left.is_relative_to(right) and not right.is_relative_to(left)
                for i, left in enumerate(roots) for right in roots[i+1:]),
            'Scientific, native and new operational checkouts must be separate')
    for name in ('plan', 'freeze', 'native_declaration', 'operational_declaration', 'metadata_directory'):
        path = _path(context[name])
        require(all(not path.is_relative_to(root) and not root.is_relative_to(path) for root in roots),
                'External declaration/freeze/metadata overlaps source: '+name)
    require(context['scientific_source_commit'] == SCIENCE_A
            and context['native_source_commit'] == NATIVE_A
            and re.fullmatch(r'[0-9a-f]{40}', context['resource_source_commit'])
            and context['resource_source_commit'] not in (SCIENCE_A, NATIVE_A)
            and context['plan_sha256'] == PLAN_SHA and context['freeze_sha256'] == FREEZE_SHA,
            'Prepared scientific/native/source identity differs')
    for name in ('native_declaration_sha256', 'operational_declaration_sha256'):
        require(re.fullmatch(r'[0-9a-f]{64}', context[name]) is not None, 'Declaration digest required')
    for arguments in (context['training_args'], context['comparison_args']):
        require(arguments.expected_commit == SCIENCE_A
                and arguments.expected_plan_sha256 == PLAN_SHA
                and arguments.expected_freeze_sha256 == FREEZE_SHA
                and arguments.plan == context['plan'] and arguments.freeze == context['freeze'],
                'Prepared callable arguments differ from the frozen source/plan')


def _check_owner(owner, context):
    require(callable(getattr(owner, 'assert_owned', None)), 'Episode owner.assert_owned required')
    owner.assert_owned()
    bindings = owner.bindings
    require(bindings['resource_scope'] == 'linux_cpu_fixture_only',
            'Fixture pipeline refuses production GPU owners')
    require(re.fullmatch(r'frontier-v8-[0-9a-f]{16,64}', bindings['attempt_id']) is not None
            and re.fullmatch(r'[0-9a-f]{32,128}', bindings['nonce']) is not None,
            'Fresh fixture attempt/nonce binding required')
    for name in ('scientific_source_commit', 'native_source_commit', 'resource_source_commit',
                 'plan_sha256', 'freeze_sha256'):
        require(bindings[name] == context[name], 'Episode/source binding differs: '+name)
    return bindings


def _completion(request, plan, preflight, validation, context, bindings, preflight_sha):
    require(set(validation) == {'completed_steps', 'consumed_rows', 'artifacts_sha256',
                                'checkpoint', 'calibration'}
            and validation['completed_steps'] == 733 and validation['consumed_rows'] == 2932,
            'Fixed-final 733x4 completion required')
    artifacts = validation['artifacts_sha256']
    calibration = validation['calibration']
    checkpoint = validation['checkpoint']
    require(set(artifacts) == {'run.json', 'summary.json', 'training.jsonl',
                               'calibration.jsonl', 'reload_check.jsonl'}
            and set(checkpoint) == {'files_sha256', 'directory_sha256'}
            and bool(checkpoint['files_sha256'])
            and set(calibration) == {'journal_sha256', 'ordered_ids_sha256', 'count', 'temperature'}
            and calibration['count'] == 496
            and type(calibration['temperature']) in (int, float)
            and math.isfinite(calibration['temperature']) and calibration['temperature'] > 0,
            'Complete fixed-final artifact/Calibration binding required')
    require(all(re.fullmatch(r'[0-9a-f]{64}', checksum) is not None for checksum in
                [*artifacts.values(), *checkpoint['files_sha256'].values(),
                 checkpoint['directory_sha256'], calibration['journal_sha256'],
                 calibration['ordered_ids_sha256'], preflight_sha]), 'Completion content digests required')
    return {'schema_version': 1, 'protocol_id': plan['protocol_id'], 'status': 'complete',
        'source_commit': SCIENCE_A, 'source_sha256': preflight['source_sha256'],
        'plan_sha256': PLAN_SHA, 'freeze_receipt_sha256': FREEZE_SHA,
        'execution_request_path': context['training_args'].request,
        'execution_request_sha256': preflight['request_sha256'],
        'training_preflight_receipt': request['task_directory']+'/cpu-preflight.json',
        'training_preflight_receipt_sha256': preflight_sha,
        'runtime_receipt_path': request['runtime_receipt'],
        'runtime_receipt_sha256': request['runtime_receipt_sha256'],
        'training_run': request['training_run'], 'runtime': plan['runtime'],
        'gpu_uuid': bindings['gpu_uuid'], 'visible_devices': bindings['visible_devices'],
        'fixed_final_checkpoint': True, 'defer_heldout': True, 'resume_training': False,
        'automatic_promotion': False, **validation}


def _comparison_request(request, context, completion):
    return {'schema_version': 1, 'protocol_id': completion['protocol_id'],
        'expected_commit': SCIENCE_A, 'plan_sha256': PLAN_SHA, 'freeze_sha256': FREEZE_SHA,
        'plan_path': context['plan'], 'freeze_path': context['freeze'],
        'dataset': request['dataset'], 'released_checkpoint': request['released_checkpoint'],
        'adapted_checkpoint': request['training_run']+'/checkpoint',
        'training_completion_receipt': request['completion_receipt'],
        'training_preflight_receipt': completion['training_preflight_receipt'],
        'training_execution_request': context['training_args'].request,
        'runtime_receipt': request['runtime_receipt'], 'resource_receipt': request['resource_receipt'],
        'output': request['comparison_output'], 'device': 'cuda:0'}


def run_cpu_fixture_pipeline(context, owner, modules):
    """Test the proposed child sequence; no production module factory is used.

    The caller, even in fixtures, consumes the fresh attempt before this call.
    Exceptions propagate to the episode's independent restoration path. All
    additional metadata is outside the scientific task. No retry, resume or
    heldout-dependent selection exists here. Input materialization can precede
    Cal fitting; the unchanged comparator ensures Cal fits precede heldout
    FORWARDS. A fixture completion wrapper is never a real training receipt.
    """
    require(isinstance(modules, CPUFixtureModules) and modules.scope == FIXTURE_SCOPE,
            'Only explicitly injected CPU fixtures are supported')
    bindings = _check_owner(owner, context)  # Before source/path callbacks.
    check_prepared_layout(context)
    verified = modules.verify_sources(context)
    require(all(verified[name] == context[name] for name in
            ('scientific_source_commit', 'native_source_commit', 'resource_source_commit',
             'native_declaration_sha256', 'operational_declaration_sha256')),
            'Injected source checker binding differs')
    owner.assert_owned()
    request, plan, preflight = modules.driver.prepare(context['training_args'], claimed=True)
    require(request['attempt_id'] == bindings['attempt_id']
            and preflight['request_sha256'] == bindings['execution_request_sha256']
            and request['runtime_receipt_sha256'] == bindings['runtime_receipt_sha256'],
            'Episode/attempt/current-stage binding differs')
    require(plan['settings']['steps'] == 733 and plan['settings']['accumulation'] == 4
            and plan['settings']['train_rows'] == 2932 and plan['settings']['defer_heldout'] is True
            and plan['settings']['checkpoint_every'] == 0, 'Frozen one-pass settings differ')
    metadata, task = _path(context['metadata_directory']), _path(request['task_directory'])
    require(not metadata.is_relative_to(task) and not task.is_relative_to(metadata)
            and not _path(context['comparison_args'].request).is_relative_to(task),
            'Additional child metadata/request must stay outside the scientific task')
    argv = modules.driver.translated_argv(plan, request)
    require(argv == preflight['resolved_training_argv'], 'Translated scientific argv differs')
    preflight_path = request['task_directory']+'/cpu-preflight.json'
    modules.write_json(preflight_path, preflight)
    preflight_sha = modules.sha(preflight_path)
    publication = {'path': request['released_checkpoint'], **plan['expected_initial_checkpoint']}
    base = {'path': request['base_snapshot'], 'cache': request['hf_cache'],
            'files_sha256': plan['expected_base_snapshot_files_sha256']}
    model_bindings = {name: bindings[name] for name in ('gpu_uuid', 'visible_devices', 'device')}
    model_bindings['source_commit'] = SCIENCE_A
    training = SimpleNamespace(**plan['settings'], data=request['dataset'], output=request['training_run'],
                               initial_checkpoint=request['released_checkpoint'], resume_training=None)
    owner.assert_owned()
    observation = modules.native.observe_training(modules.trainer, plan, model_bindings,
        publication, base, context['scientific_root'], assert_owned=owner.assert_owned)
    require(isinstance(observation, AbstractContextManager), 'Observation context manager required')
    with observation as observed:
        modules.trainer.run(training)
    owner.assert_owned()
    validation = modules.driver.validate_completed_run(request['training_run'], plan, preflight)
    completion = _completion(request, plan, preflight, validation, context, bindings, preflight_sha)
    modules.write_json(request['completion_receipt'], completion)
    modules.write_json(str(metadata/'training-observation.json'), observed)
    comparison_request = _comparison_request(request, context, completion)
    modules.write_json(context['comparison_args'].request, comparison_request)
    owner.assert_owned()
    comparison = modules.comparator.preflight(context['comparison_args'])
    scoring = comparison['bindings']
    require(all(scoring[name] == model_bindings[name] for name in model_bindings)
            and scoring['runtime'] == plan['runtime']
            and scoring['plan_sha256'] == PLAN_SHA and scoring['freeze_receipt_sha256'] == FREEZE_SHA
            and scoring['checkpoint_directory_sha256'] == {
                'released': publication['directory_sha256'], 'adapted': validation['checkpoint']['directory_sha256']},
            'Comparison phase binding differs')
    owner.assert_owned()
    rows, calibration = modules.read_comparison_inputs(request, plan)
    checkpoints = {'released': publication,
                   'adapted': {'path': comparison_request['adapted_checkpoint'], **validation['checkpoint']}}
    loader = modules.native.make_loader(plan, scoring, checkpoints, base, context['scientific_root'],
                                        assert_owned=owner.assert_owned)
    manifest = modules.comparator.score_bundle(plan, rows, calibration,
        scoring['checkpoint_directory_sha256'], scoring, request['comparison_output'], loader)
    owner.assert_owned()
    return {'status': 'CPU_fixture_scientific_child_contract_complete_no_execution_authority',
            'scope': FIXTURE_SCOPE, 'prepared_training_argv': argv,
            'fixture_completion_wrapper': completion, 'fixture_comparison_manifest': manifest,
            'fixture_loader_audits': loader.audits, 'execution_available': False,
            'resource_authority': False, 'actual_training_runs': 0, 'model_calls': 0,
            'actual_business_executions': 0, 'automatic_promotion': False,
            'provenance': {'source_verification': 'injected_CPU_fixture',
                           'training_preflight_run_and_completion_validation': 'injected_CPU_fixture',
                           'native_observer_loader_and_logits': 'injected_CPU_fixture',
                           'comparison': 'supplied_CPU_callback_original_score_bundle_in_integration_test'},
            'limits': ['Injected CPU callbacks and logits do not prove installed modules, real tensors, '
                       'gradients, GPU ownership or restored original queue.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--request')
    parser.parse_args(argv)
    execute_child()  # No path is opened and no episode attempt is consumed.


if __name__ == '__main__':
    main()
