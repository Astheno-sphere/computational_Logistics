"""Optional native adapters for the frozen v8 callables; no execution CLI.

The owner supplies a live ``assert_owned()`` callback which raises on loss of
authority. This module and CPU fake dependencies cannot establish a GPU lease
or queue-restoration authority. Operational code must live outside the clean
Source A checkout. Training observation delegates to the original initializer
and AdamW instance; it adds no model calls, backward calls or optimizer steps.

First-step policy, declared before any model call: every PRESENT trainable
gradient is finite, absent gradients are counted without imputation, each of
LoRA-A/LoRA-B/head has at least one pooled nonzero element, and base gradients
are all absent. A scalar Choice head bias may have a zero gradient.
"""
from contextlib import contextmanager
import gc
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace
import weakref


SOURCE_A = 'd8eeb3d1f8e8d8751476f102ab456170c277e86a'
NUMERICS = {'backbone_dtype': 'torch.bfloat16', 'head_dtype': 'torch.float32',
    'cuda': '12.8', 'float32_matmul_precision': 'highest', 'tf32': False,
    'tf32_scope': 'torch.backends.cuda.matmul.allow_tf32', 'quantization': False}
JEV_OVERRIDES = ('JEV_TORCH_DTYPE', 'JEV_LOAD_8BIT', 'JEV_LOAD_4BIT',
                 'JEV_DEVICE_MAP', 'JEV_MAX_MEMORY', 'JEV_ALLOW_OFFLOAD')
MEMORY_SCOPE = 'model_loaded_row_forward_and_cpu_logits'
BASE_PREFIX = 'model.language_model.'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 << 20), b''):
            result.update(block)
    return result.hexdigest()


def verify_inventory(spec, *, cache=None):
    """Verify supplied complete file hashes, using the frozen directory hash."""
    root = Path(spec['path'])
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),
            'Regular absolute input directory required')
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            require(cache is not None and path.resolve().is_relative_to(Path(cache).resolve())
                    and path.is_file(), 'Snapshot link outside declared cache')
        elif path.is_dir():
            continue
        require(path.is_file(), 'Nonregular input leaf')
        files[path.relative_to(root).as_posix()] = file_sha(path)
    require(files == spec['files_sha256'], 'Input fullhash inventory differs')
    if cache is None:
        digest = hashlib.sha256()
        for name in sorted(files):
            digest.update(name.encode()+b'\0')
            with (root/name).open('rb') as handle:
                for block in iter(lambda: handle.read(8 << 20), b''):
                    digest.update(block)
        require(digest.hexdigest() == spec['directory_sha256'], 'Checkpoint directory hash differs')
    return root


def verify_scientific_root(scientific_root, plan, bindings):
    root = Path(scientific_root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),
            'Regular absolute scientific root required')
    require(bindings['source_commit'] == SOURCE_A, 'Scientific source is not Source A')
    environment = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args],
            env=environment, stderr=subprocess.DEVNULL).decode().strip()
    require(Path(git('rev-parse', '--show-toplevel')).resolve() == root.resolve()
            and git('rev-parse', 'HEAD') == SOURCE_A, 'Scientific checkout differs from Source A')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Scientific checkout is dirty')
    for name, expected in plan['implementation_sha256'].items():
        path = root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts
                and path.is_file() and not path.is_symlink() and file_sha(path) == expected,
                'Scientific file differs: '+name)
    return root


def loaded_scientific_origins():
    return {name: getattr(module, '__file__', None) for name, module in list(sys.modules.items())
            if name == 'jev' or name.startswith('jev.') or name.startswith('scripts.')}


def validate_scientific_imports(scientific_root, plan, origins=None):
    """Check already-loaded science modules without importing missing modules."""
    origins = loaded_scientific_origins() if origins is None else origins
    checked = {}
    for name, filename in origins.items():
        relative = 'jev/__init__.py' if name == 'jev' else name.replace('.', '/')+'.py'
        if name.startswith('scripts.') and relative not in plan['implementation_sha256']:
            continue  # Separately declared operational code is outside Source A.
        require(relative in plan['implementation_sha256'] and filename is not None
                and Path(filename).resolve() == Path(scientific_root).resolve()/relative
                and file_sha(filename) == plan['implementation_sha256'][relative],
                'Scientific dependency import differs: '+name)
        checked[name] = {'path': str(Path(filename).resolve()),
                         'sha256': plan['implementation_sha256'][relative]}
    return checked


@contextmanager
def owned_environment(base_snapshot):
    changes = {name: None for name in JEV_OVERRIDES}
    changes.update(HF_HUB_CACHE=str(Path(base_snapshot['cache']).resolve()),
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                   TRANSFORMERS_CACHE=None, HUGGINGFACE_HUB_CACHE=None)
    previous = {name: os.environ.get(name) for name in changes}
    try:
        for name, value in changes.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def load_dependencies(scientific_root, base_snapshot, plan, factory=None):
    """Called only after the owner check; tests inject explicitly fake modules."""
    if factory is None:
        validate_scientific_imports(scientific_root, plan)
        import torch
        from jev import model as model_module
        from peft import get_peft_model_state_dict
        from safetensors import safe_open
        from huggingface_hub.constants import HF_HUB_CACHE
        versions = {name: metadata.version(name) for name in
                    ('transformers', 'peft', 'triton', 'safetensors', 'accelerate')}
        versions['torch'] = str(torch.__version__)
        dependencies = SimpleNamespace(torch=torch, model_class=model_module.DecisionModel,
            model_file=model_module.__file__, adapter_state=get_peft_model_state_dict,
            safe_open=safe_open, runtime=versions, hub_cache=HF_HUB_CACHE,
            local_origins=loaded_scientific_origins, scope='installed_native_runtime_external_owner_required')
    else:
        dependencies = factory()
        require(dependencies.scope == 'cpu_fakes_no_resource_authority', 'Dependency injection is CPU-fake-only')
    require(Path(dependencies.model_file).resolve() == Path(scientific_root).resolve()/'jev/model.py',
            'Scientific model import location differs')
    require(Path(dependencies.hub_cache).resolve() == Path(base_snapshot['cache']).resolve(),
            'Imported HF cache differs from the staged snapshot cache')
    validate_scientific_imports(scientific_root, plan, dependencies.local_origins())
    return dependencies


def apply_numerical_settings(torch, plan, bindings, runtime):
    require(plan['runtime_settings'] == NUMERICS and runtime == plan['runtime']
            and str(torch.__version__) == runtime['torch'], 'Frozen numerical/runtime identity differs')
    require(bindings['device'] == 'cuda:0'
            and isinstance(bindings['visible_devices'], str)
            and bool(bindings['visible_devices']) and ',' not in bindings['visible_devices']
            and os.environ.get('CUDA_VISIBLE_DEVICES') == bindings['visible_devices'],
            'Exactly one bound visible CUDA device required')
    require(torch.cuda.is_available() and torch.version.cuda == NUMERICS['cuda']
            and torch.cuda.device_count() == 1, 'Bound CUDA runtime unavailable or differs')
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.cuda.set_device(bindings['device'])
    require(torch.get_float32_matmul_precision() == 'highest'
            and torch.backends.cuda.matmul.allow_tf32 is False, 'Numerical settings were not applied')
    properties = torch.cuda.get_device_properties(bindings['device'])
    actual_uuid = str(properties.uuid)
    if not actual_uuid.startswith('GPU-'):
        actual_uuid = 'GPU-'+actual_uuid
    require(re.fullmatch(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', actual_uuid)
            and actual_uuid == bindings['gpu_uuid'] and properties.total_memory > 0,
            'Physical GPU UUID/capacity differs')
    return {'runtime': runtime, 'device': bindings['device'], 'gpu_uuid': actual_uuid,
            'visible_devices': bindings['visible_devices'], **NUMERICS,
            'gpu_capacity_bytes': int(properties.total_memory)}


def parameter_group(name):
    if name.startswith('head.'):
        return 'head'
    if '.lora_A.' in name:
        return 'lora_A'
    if '.lora_B.' in name:
        return 'lora_B'
    return 'base'


def audit_loaded_model(model, checkpoint, base_snapshot, plan, device, dependencies, scientific_root, *, training):
    torch = dependencies.torch
    require((model.model_id, model.revision, model.max_length, model.lora_rank) ==
            tuple(plan['settings'][name] for name in ('model', 'revision', 'max_length', 'lora_rank')),
            'Loaded model identity differs')
    require(not getattr(model.backbone, 'is_loaded_in_8bit', False)
            and not getattr(model.backbone, 'is_loaded_in_4bit', False), 'Quantized model rejected')
    require(set(model.backbone.peft_config) == {'default'}
            and list(model.backbone.active_adapters) == ['default'], 'Unexpected/inactive adapter')
    adapter_modules = 0
    for _, module in model.backbone.named_modules():
        if hasattr(module, 'lora_A') or hasattr(module, 'lora_B'):
            require(set(module.lora_A) == set(module.lora_B) == {'default'}
                    and list(module.active_adapters) == ['default']
                    and not module.disable_adapters and not module.merged
                    and not module.merged_adapters, 'Adapter disabled or merged')
            adapter_modules += 1
    require(adapter_modules > 0, 'No active LoRA modules')
    parameters = dict(model.named_parameters())
    flags, base = {}, {}
    for name, parameter in parameters.items():
        group = parameter_group(name)
        require(str(parameter.device) == device, 'Parameter off controlled device: '+name)
        require(parameter.dtype == (torch.bfloat16 if group == 'base' else torch.float32),
                'Parameter dtype differs: '+name)
        require(not parameter.requires_grad if group == 'base' else
                (parameter.requires_grad if training else True), 'Training/frozen flag differs: '+name)
        flags[name] = bool(parameter.requires_grad)
        if group == 'base':
            require(name.startswith('backbone.base_model.model.'), 'Unmapped base parameter: '+name)
            key = BASE_PREFIX+name.removeprefix('backbone.base_model.model.').replace('.base_layer.', '.')
            require(key not in base, 'Duplicate base tensor mapping')
            base[key] = parameter
    exact_counts = {'head': 0, 'adapter': 0, 'base': 0}
    def compare(actual, expected, group, name):
        required_dtype = torch.bfloat16 if group == 'base' else torch.float32
        require(actual.dtype == expected.dtype == required_dtype and actual.shape == expected.shape,
                'Tensor dtype/shape differs: '+name)
        require(torch.equal(actual.detach().cpu(), expected), 'Tensor values differ: '+name)
        exact_counts[group] += 1
    head = torch.load(Path(checkpoint['path'])/'head.pt', map_location='cpu', weights_only=True)
    actual_head = model.head.state_dict()
    require(set(head) == set(actual_head) == {'weight', 'bias'}, 'Head tensor key set differs')
    for name in head:
        compare(actual_head[name], head[name], 'head', name)
    actual_adapter = dependencies.adapter_state(model.backbone, adapter_name='default')
    with dependencies.safe_open(Path(checkpoint['path'])/'adapter/adapter_model.safetensors',
                                framework='pt', device='cpu') as saved:
        require(set(saved.keys()) == set(actual_adapter), 'Adapter tensor key set differs')
        require(bool(actual_adapter) and all('.lora_A.' in key or '.lora_B.' in key for key in actual_adapter),
                'Unexpected adapter tensors')
        for name, actual in actual_adapter.items():
            compare(actual, saved.get_tensor(name), 'adapter', name)
    snapshot = Path(base_snapshot['path'])
    index = json.loads((snapshot/'model.safetensors.index.json').read_text())['weight_map']
    expected_base = {name for name in index if name.startswith(BASE_PREFIX)}
    require(set(base) == expected_base and bool(base), 'Retained base tensor key set differs')
    for filename in sorted({index[name] for name in base}):
        require(filename in base_snapshot['files_sha256'], 'Uninventoried base shard')
        with dependencies.safe_open(snapshot/filename, framework='pt', device='cpu') as saved:
            for name in sorted(base):
                if index[name] == filename:
                    compare(base[name], saved.get_tensor(name), 'base', name)
    return {'status': 'loaded_tensors_exact', 'training': training,
            'checkpoint_directory_sha256': checkpoint['directory_sha256'],
            'exact_tensor_counts': exact_counts, 'adapter_modules': adapter_modules,
            'active_adapter': 'default', 'merged': False, 'parameter_requires_grad': flags,
            'device': device, 'backbone_dtype': 'torch.bfloat16', 'trainable_dtype': 'torch.float32',
            'dependency_scope': dependencies.scope,
            'scientific_imports': validate_scientific_imports(scientific_root, plan, dependencies.local_origins())}


def prepare_native(plan, bindings, checkpoint, base_snapshot, scientific_root, assert_owned, factory):
    require(callable(assert_owned), 'Live owner callback required')
    assert_owned()
    root = verify_scientific_root(scientific_root, plan, bindings)
    verify_inventory(checkpoint)
    require(base_snapshot['files_sha256'] == plan['expected_base_snapshot_files_sha256'],
            'Base snapshot differs from scientific plan')
    cache = Path(base_snapshot['cache'])
    require(cache.is_absolute() and cache.is_dir() and not cache.is_symlink()
            and Path(base_snapshot['path']).resolve().is_relative_to(cache.resolve())
            and Path(base_snapshot['path']).name == plan['settings']['revision'], 'Pinned snapshot/cache differs')
    verify_inventory(base_snapshot, cache=cache)
    assert_owned()
    dependencies = load_dependencies(root, base_snapshot, plan, factory)
    assert_owned()
    runtime = apply_numerical_settings(dependencies.torch, plan, bindings, dependencies.runtime)
    return dependencies, runtime


def make_loader(plan, bindings, checkpoints, base_snapshot, scientific_root, *, assert_owned, dependencies=None):
    """Return the frozen score_bundle loader; ``loader.audits`` has no tensors.

    Checkpoint specs have path/files_sha256/directory_sha256; snapshot specs
    have path/cache/files_sha256. Optional dependencies is a lazy fake factory
    for CPU tests. The external owner must bind real installed package origins.
    Four calls/Cal fitting order remain entirely with the frozen comparator.
    """
    audits = []
    @contextmanager
    def loader(weight, phase):
        require(weight in ('released', 'adapted') and phase in ('calibration', 'heldout'),
                'Unknown frozen weight/phase')
        checkpoint = checkpoints[weight]
        require(checkpoint['directory_sha256'] == bindings['checkpoint_directory_sha256'][weight],
                'Checkpoint binding differs')
        if weight == 'released':
            require(checkpoint['files_sha256'] == plan['expected_initial_checkpoint']['files_sha256']
                    and checkpoint['directory_sha256'] == plan['expected_initial_checkpoint']['directory_sha256'],
                    'Publication checkpoint differs')
        model = None
        native = None
        with owned_environment(base_snapshot):
            try:
                native, runtime = prepare_native(plan, bindings, checkpoint, base_snapshot,
                                                scientific_root, assert_owned, dependencies)
                assert_owned()
                start = time.perf_counter()
                model = native.model_class.load(checkpoint['path'], device=bindings['device'])
                native.torch.cuda.synchronize(bindings['device'])
                loading_seconds = time.perf_counter()-start
                audit = audit_loaded_model(model, checkpoint, base_snapshot, plan, bindings['device'],
                                           native, scientific_root, training=False)
                require(not model.training, 'Loaded comparison model is not eval')
                audits.append({'weight': weight, 'phase': phase, **audit})
                runtime = {**runtime, 'weight': weight, 'phase': phase, 'loading_seconds': loading_seconds}
                def predict(row):
                    assert_owned()
                    require(model is not None, 'Loader context is closed')
                    validate_scientific_imports(scientific_root, plan, native.local_origins())
                    torch, device = native.torch, bindings['device']
                    torch.cuda.synchronize(device)
                    memory = {'allocated_baseline_bytes': torch.cuda.memory_allocated(device),
                              'reserved_baseline_bytes': torch.cuda.memory_reserved(device)}
                    torch.cuda.reset_peak_memory_stats(device)
                    with torch.inference_mode():
                        start = time.perf_counter()
                        logits = model([row])[0].float().cpu()
                        torch.cuda.synchronize(device)
                        duration = time.perf_counter()-start
                    memory.update(allocated_peak_bytes=torch.cuda.max_memory_allocated(device),
                                  reserved_peak_bytes=torch.cuda.max_memory_reserved(device), scope=MEMORY_SCOPE)
                    values = logits.tolist()
                    require(len(values) == len(row['options']) and all(math.isfinite(v) for v in values)
                            and math.isfinite(duration) and duration >= 0, 'Invalid native row output')
                    return {'logits': values, 'latency_seconds': duration, 'cuda_memory': memory}
                yield runtime, predict
            finally:
                model = None
                gc.collect()
                if native is not None:
                    native.torch.cuda.empty_cache()
    loader.audits = audits
    return loader


def audit_first_gradients(model, torch):
    groups = {name: {'none_parameters': 0, 'zero_parameters': 0, 'nonzero_parameters': 0,
                     'present_elements': 0, 'nonzero_elements': 0}
              for name in ('lora_A', 'lora_B', 'head')}
    base_parameters = 0
    for name, parameter in model.named_parameters():
        group = parameter_group(name)
        gradient = parameter.grad
        if group == 'base':
            base_parameters += 1
            require(gradient is None, 'Frozen base received gradient: '+name)
            continue
        require(parameter.requires_grad and parameter.dtype == torch.float32, 'Unexpected trainable parameter')
        counts = groups[group]
        if gradient is None:
            counts['none_parameters'] += 1
            continue
        require(gradient.dtype == torch.float32 and torch.isfinite(gradient).all().item(),
                'Nonfinite/wrong-dtype present gradient: '+name)
        nonzero = int(torch.count_nonzero(gradient).item())
        counts['present_elements'] += gradient.numel()
        counts['nonzero_elements'] += nonzero
        counts['nonzero_parameters' if nonzero else 'zero_parameters'] += 1
    require(base_parameters > 0 and all(values['nonzero_elements'] >= 1 for values in groups.values()),
            'First-step pooled gradient group is zero or absent')
    return {'status': 'first_original_accumulated_step_gradients_passed',
            'policy': 'all_present_finite_none_reported_pooled_nonzero_at_least_one_per_A_B_head_base_none',
            'groups': groups, 'base_parameters': base_parameters, 'base_present_gradients': 0,
            'every_trainable_parameter_required_to_have_gradient': False,
            'trainable_parameters_without_gradient': sum(v['none_parameters'] for v in groups.values())}


@contextmanager
def observe_training(train_module, plan, bindings, publication, base_snapshot, scientific_root,
                     *, assert_owned, dependencies=None):
    """Observe unchanged run(args); restore child-local bindings on every exit."""
    require(publication['files_sha256'] == plan['expected_initial_checkpoint']['files_sha256']
            and publication['directory_sha256'] == plan['expected_initial_checkpoint']['directory_sha256'],
            'Training initializer is not the publication')
    state = {'status': 'training_observer_entered', 'optimizer_pre_step_observations': 0,
             'loaded_audit': None, 'first_gradient_audit': None}
    model_ref, hook = None, None
    with owned_environment(base_snapshot):
        native, _ = prepare_native(plan, bindings, publication, base_snapshot, scientific_root,
                                   assert_owned, dependencies)
        require(Path(train_module.__file__).resolve() == Path(scientific_root).resolve()/'jev/train.py',
                'Scientific training import location differs')
        state['dependency_scope'] = native.scope
        original_initialize, original_adamw = train_module.initialize_model, native.torch.optim.AdamW
        def initialize(args, model_class, initial_checkpoint):
            nonlocal model_ref
            assert_owned()
            validate_scientific_imports(scientific_root, plan, native.local_origins())
            require(model_ref is None and model_class is native.model_class, 'Unexpected/repeated model initializer')
            require(all(getattr(args, name) == value for name, value in plan['settings'].items())
                    and not getattr(args, 'resume_training', None)
                    and Path(args.initial_checkpoint).resolve() == Path(publication['path']).resolve(),
                    'Frozen training arguments differ')
            model = original_initialize(args, model_class, initial_checkpoint)
            model_ref = weakref.ref(model)
            state['loaded_audit'] = audit_loaded_model(model, publication, base_snapshot, plan,
                                                      bindings['device'], native, scientific_root, training=True)
            return model
        def adamw(*args, **kwargs):
            nonlocal hook
            assert_owned()
            require(model_ref is not None and model_ref() is not None and hook is None,
                    'Unexpected/repeated AdamW construction')
            optimizer = original_adamw(*args, **kwargs)
            def before_step(optimizer, args, kwargs):
                assert_owned()
                validate_scientific_imports(scientific_root, plan, native.local_origins())
                state['optimizer_pre_step_observations'] += 1
                if state['optimizer_pre_step_observations'] == 1:
                    model = model_ref()
                    require(model is not None, 'Training model disappeared before first gradient observation')
                    state['first_gradient_audit'] = audit_first_gradients(model, native.torch)
                return None
            hook = optimizer.register_step_pre_hook(before_step)
            return optimizer
        train_module.initialize_model, native.torch.optim.AdamW = initialize, adamw
        try:
            yield state
            require(state['loaded_audit'] is not None and state['first_gradient_audit'] is not None
                    and state['optimizer_pre_step_observations'] == plan['settings']['steps'],
                    'Training observation incomplete')
            state['status'] = 'training_observer_complete_pending_original_journal_validation'
        except BaseException:
            state['status'] = 'training_observer_failed'
            raise
        finally:
            train_module.initialize_model, native.torch.optim.AdamW = original_initialize, original_adamw
            if hook is not None:
                hook.remove()
