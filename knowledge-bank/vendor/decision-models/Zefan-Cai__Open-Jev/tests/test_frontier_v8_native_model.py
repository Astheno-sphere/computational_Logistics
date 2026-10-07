"""CPU-only fake native contracts; no Torch import or resource authority."""
from contextlib import nullcontext
import gc
import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref

from scripts import frontier_v8_native_model as native


UUID = 'GPU-01234567-89ab-cdef-0123-456789abcdef'
A = 'base_model.model.layers.0.self_attn.q_proj.lora_A.weight'
B = 'base_model.model.layers.0.self_attn.q_proj.lora_B.weight'
BASE = native.BASE_PREFIX+'layers.0.self_attn.q_proj.weight'
EMBED = native.BASE_PREFIX+'embed_tokens.weight'


class FakeTensor:
    def __init__(self, values, shape=None, dtype='torch.float32', device='cpu', requires_grad=False):
        self.values = list(values)
        self.shape = tuple(shape or (len(self.values),))
        self.dtype, self.device, self.requires_grad = dtype, device, requires_grad
        self.grad = None

    def detach(self):
        return self

    def cpu(self):
        return FakeTensor(self.values, self.shape, self.dtype)

    def float(self):
        return self.to(dtype='torch.float32')

    def to(self, *, dtype):
        return FakeTensor(self.values, self.shape, dtype, self.device)

    def tolist(self):
        return self.values[:]

    def numel(self):
        return len(self.values)


class FakeValue:
    def __init__(self, value):
        self.value = value

    def all(self):
        return self

    def item(self):
        return self.value


class FakeHandle:
    def __init__(self, optimizer, callback):
        self.optimizer, self.callback, self.removed = optimizer, callback, False

    def remove(self):
        self.optimizer.hooks.remove(self.callback)
        self.removed = True


class FakeOptimizer:
    def __init__(self, args, kwargs):
        self.args, self.kwargs, self.hooks, self.steps = args, kwargs, [], 0

    def register_step_pre_hook(self, callback):
        self.hooks.append(callback)
        self.handle = FakeHandle(self, callback)
        return self.handle

    def step(self):
        for callback in self.hooks:
            if callback(self, (), {}) is not None:
                raise AssertionError('Observer changed optimizer arguments')
        self.steps += 1


class FakeCuda:
    def __init__(self):
        self.uuid, self.count, self.events, self.emptied = UUID, 1, [], 0

    def is_available(self):
        return True

    def device_count(self):
        return self.count

    def set_device(self, device):
        self.events.append('set_device')

    def get_device_properties(self, device):
        return SimpleNamespace(uuid=self.uuid, total_memory=80 << 30)

    def synchronize(self, device):
        self.events.append('sync')

    def memory_allocated(self, device):
        self.events.append('allocated_baseline')
        return 100

    def memory_reserved(self, device):
        self.events.append('reserved_baseline')
        return 150

    def reset_peak_memory_stats(self, device):
        self.events.append('reset_peaks')

    def max_memory_allocated(self, device):
        self.events.append('allocated_peak')
        return 120

    def max_memory_reserved(self, device):
        self.events.append('reserved_peak')
        return 170

    def empty_cache(self):
        self.emptied += 1


class FakeTorch:
    bfloat16, float32, __version__ = 'torch.bfloat16', 'torch.float32', '2.8.0+cu128'

    def __init__(self, head):
        self.cuda, self.head = FakeCuda(), head
        self.version = SimpleNamespace(cuda='12.8')
        self.backends = SimpleNamespace(cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True)))
        self.precision, self.optimizers, self.load_arguments = 'medium', [], []
        self.optim = SimpleNamespace(AdamW=self.original_adamw)

    def original_adamw(self, *args, **kwargs):
        optimizer = FakeOptimizer(args, kwargs)
        self.optimizers.append(optimizer)
        return optimizer

    def set_float32_matmul_precision(self, value):
        self.precision = value

    def get_float32_matmul_precision(self):
        return self.precision

    def load(self, path, **kwargs):
        self.load_arguments.append((str(path), kwargs))
        return self.head

    def inference_mode(self):
        return nullcontext()

    def equal(self, a, b):
        return a.values == b.values and a.shape == b.shape and a.dtype == b.dtype

    def isfinite(self, tensor):
        return FakeValue(all(math.isfinite(value) for value in tensor.values))

    def count_nonzero(self, tensor):
        return FakeValue(sum(value != 0 for value in tensor.values))


class FakeSafeFile:
    def __init__(self, tensors):
        self.tensors = tensors

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def keys(self):
        return self.tensors.keys()

    def get_tensor(self, name):
        return self.tensors[name]


class FixtureModel:
    def __init__(self, fixture):
        self.model_id, self.revision, self.max_length, self.lora_rank = (
            fixture.plan['settings'][name] for name in ('model', 'revision', 'max_length', 'lora_rank'))
        self.training, self.forward_calls, self.fixture = False, 0, fixture
        self.parameters = {
            'backbone.base_model.model.embed_tokens.weight': FakeTensor([1, 2, 3, 4], (2, 2), 'torch.bfloat16', 'cuda:0'),
            'backbone.base_model.model.layers.0.self_attn.q_proj.base_layer.weight': FakeTensor([4, 3, 2, 1], (2, 2), 'torch.bfloat16', 'cuda:0'),
            'backbone.'+A.replace('.lora_A.', '.lora_A.default.'): FakeTensor(range(16), (8, 2), device='cuda:0'),
            'backbone.'+B.replace('.lora_B.', '.lora_B.default.'): FakeTensor(range(16), (2, 8), device='cuda:0'),
            'head.weight': FakeTensor([2, 3], (1, 2), device='cuda:0', requires_grad=True),
            'head.bias': FakeTensor([0], (1,), device='cuda:0', requires_grad=True),
        }
        self.head = SimpleNamespace(state_dict=lambda: {
            key.removeprefix('head.'): tensor for key, tensor in self.parameters.items() if key.startswith('head.')})
        self.adapter_module = SimpleNamespace(lora_A={'default': True}, lora_B={'default': True},
            active_adapters=['default'], disable_adapters=False, merged=False, merged_adapters=[])
        self.backbone = SimpleNamespace(peft_config={'default': True}, active_adapters=['default'],
            named_modules=lambda: [('adapter', self.adapter_module)])

    def named_parameters(self):
        return self.parameters.items()

    def __call__(self, rows):
        self.forward_calls += 1
        self.fixture.torch.cuda.events.append('forward')
        return [FakeTensor([0.25, -0.75], device='cuda:0')]


class NativeModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scientific = self.root/'scientific'
        (self.scientific/'jev').mkdir(parents=True)
        scientific_files = ('__init__.py', 'model.py', 'train.py', 'api.py', 'metrics.py', 'data.py', 'prefix_cache.py')
        for name in scientific_files:
            (self.scientific/'jev'/name).write_text('Explicit CPU scientific fixture, never executed.\n')
        self.plan = json.loads((Path(__file__).resolve().parents[1]/
            'reports/frontier-v8-training-protocol-20261003/training-plan.json').read_text())
        self.plan['implementation_sha256'] = {f'jev/{name}': native.file_sha(self.scientific/'jev'/name)
                                               for name in scientific_files}
        self.origins = {'jev' if name == '__init__.py' else 'jev.'+name.removesuffix('.py'):
                        str(self.scientific/'jev'/name) for name in scientific_files}
        self.checkpoint = self.root/'checkpoint'; (self.checkpoint/'adapter').mkdir(parents=True)
        for name in ('model.json', 'head.pt', 'temperature.json', 'adapter/adapter_config.json',
                     'adapter/adapter_model.safetensors'):
            (self.checkpoint/name).write_text('Explicit CPU checkpoint fixture, never loaded by Torch.\n')
        self.cache = self.root/'cache'
        self.snapshot = self.cache/'snapshots'/self.plan['settings']['revision']
        self.snapshot.mkdir(parents=True)
        (self.snapshot/'base.safetensors').write_text('Explicit CPU base tensor fixture.\n')
        (self.snapshot/'model.safetensors.index.json').write_text(json.dumps({'weight_map': {
            EMBED: 'base.safetensors', BASE: 'base.safetensors'}}))
        self.publication = self.checkpoint_spec(self.checkpoint)
        self.plan['expected_initial_checkpoint'] = {
            'files_sha256': self.publication['files_sha256'],
            'directory_sha256': self.publication['directory_sha256']}
        self.base = {'path': str(self.snapshot), 'cache': str(self.cache),
                     'files_sha256': self.files(self.snapshot)}
        self.plan['expected_base_snapshot_files_sha256'] = self.base['files_sha256']
        self.bindings = {'source_commit': native.SOURCE_A, 'device': 'cuda:0',
                         'visible_devices': UUID, 'gpu_uuid': UUID,
                         'checkpoint_directory_sha256': {
                             weight: self.publication['directory_sha256'] for weight in ('released', 'adapted')}}
        self.saved_head = {'weight': FakeTensor([2, 3], (1, 2)), 'bias': FakeTensor([0], (1,))}
        self.saved_adapter = {A: FakeTensor(range(16), (8, 2)), B: FakeTensor(range(16), (2, 8))}
        self.saved_base = {EMBED: FakeTensor([1, 2, 3, 4], (2, 2), 'torch.bfloat16'),
                           BASE: FakeTensor([4, 3, 2, 1], (2, 2), 'torch.bfloat16')}
        self.torch = FakeTorch(self.saved_head)
        self.models, self.owner_checks, self.dependency_calls = [], 0, 0
        fixture = self
        class ModelClass:
            @classmethod
            def load(cls, path, device='cuda:0'):
                model = FixtureModel(fixture)
                fixture.models.append(model)
                return model
        self.model_class = ModelClass
        self.environment = patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': UUID})
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.git = patch.object(native.subprocess, 'check_output', side_effect=self.fake_git)
        self.git.start(); self.addCleanup(self.git.stop)

    def files(self, root):
        return {path.relative_to(root).as_posix(): native.file_sha(path)
                for path in root.rglob('*') if path.is_file()}

    def checkpoint_spec(self, root):
        files = self.files(root)
        digest = hashlib.sha256()
        for name in sorted(files):
            digest.update(name.encode()+b'\0'); digest.update((root/name).read_bytes())
        return {'path': str(root), 'files_sha256': files, 'directory_sha256': digest.hexdigest()}

    def fake_git(self, args, **kwargs):
        command = args[3:]
        if command == ['rev-parse', '--show-toplevel']:
            return str(self.scientific).encode()
        if command == ['rev-parse', 'HEAD']:
            return native.SOURCE_A.encode()
        if command == ['status', '--porcelain', '--untracked-files=all']:
            return b''
        raise AssertionError(command)

    def assert_owned(self):
        self.owner_checks += 1

    def dependencies(self):
        self.dependency_calls += 1
        return SimpleNamespace(torch=self.torch, model_class=self.model_class,
            model_file=str(self.scientific/'jev/model.py'), runtime=self.plan['runtime'],
            local_origins=lambda: self.origins, scope='cpu_fakes_no_resource_authority',
            hub_cache=str(self.cache), adapter_state=lambda model, **kwargs: {
                A: self.models[-1].parameters['backbone.'+A.replace('.lora_A.', '.lora_A.default.')],
                B: self.models[-1].parameters['backbone.'+B.replace('.lora_B.', '.lora_B.default.')]},
            safe_open=lambda path, **kwargs: FakeSafeFile(
                self.saved_adapter if Path(path).name == 'adapter_model.safetensors' else self.saved_base))

    def loader(self, owner=None, dependencies=None):
        return native.make_loader(self.plan, self.bindings,
            {weight: self.publication for weight in ('released', 'adapted')}, self.base, self.scientific,
            assert_owned=owner or self.assert_owned, dependencies=dependencies or self.dependencies)

    def training(self):
        def original_initialize(args, model_class, checkpoint):
            model = model_class.load(args.initial_checkpoint)
            for name, parameter in model.named_parameters():
                parameter.requires_grad = native.parameter_group(name) != 'base'
            return model
        module = SimpleNamespace(__file__=str(self.scientific/'jev/train.py'),
                                 initialize_model=original_initialize)
        args = SimpleNamespace(**self.plan['settings'], initial_checkpoint=str(self.checkpoint), resume_training=None)
        return module, args

    def gradients(self, model, *, bias=None):
        for name, parameter in model.named_parameters():
            if native.parameter_group(name) == 'base':
                continue
            if name == 'head.bias' and bias is None:
                continue
            parameter.grad = FakeTensor(([bias] if name == 'head.bias' else
                [1]+[0]*(parameter.numel()-1)), parameter.shape, device='cuda:0')

    def test_import_is_lazy_and_owner_failure_precedes_dependencies(self):
        def denied():
            raise RuntimeError('No live lease; CPU fakes have no authority')
        with self.assertRaisesRegex(RuntimeError, 'No live lease'):
            with self.loader(owner=denied)('released', 'calibration'):
                self.fail('Unowned loader entered')
        self.assertEqual(self.dependency_calls, 0)
        self.assertEqual(self.models, [])
        self.assertEqual(self.torch.cuda.events, [])

    def test_exact_runtime_row_scope_original_flags_and_cleanup(self):
        loader = self.loader()
        with loader('released', 'calibration') as (runtime, predict):
            self.assertEqual(set(runtime), {'runtime', 'device', 'gpu_uuid', 'visible_devices',
                'backbone_dtype', 'head_dtype', 'cuda', 'float32_matmul_precision', 'tf32',
                'tf32_scope', 'quantization', 'gpu_capacity_bytes', 'weight', 'phase', 'loading_seconds'})
            self.assertEqual(runtime['backbone_dtype'], 'torch.bfloat16')
            self.assertFalse(runtime['tf32'])
            self.torch.cuda.events.clear()
            result = predict({'options': ['a', 'b']})
            self.assertEqual(result['logits'], [0.25, -0.75])
            self.assertEqual(result['cuda_memory'], {'allocated_baseline_bytes': 100,
                'reserved_baseline_bytes': 150, 'allocated_peak_bytes': 120,
                'reserved_peak_bytes': 170, 'scope': native.MEMORY_SCOPE})
            self.assertEqual(self.torch.cuda.events, ['sync', 'allocated_baseline', 'reserved_baseline',
                'reset_peaks', 'forward', 'sync', 'allocated_peak', 'reserved_peak'])
            self.assertEqual(self.models[-1].forward_calls, 1)
        self.assertEqual(self.torch.cuda.emptied, 1)
        self.assertEqual(loader.audits[0]['exact_tensor_counts'], {'head': 2, 'adapter': 2, 'base': 2})
        self.assertTrue(loader.audits[0]['parameter_requires_grad']['head.bias'])
        self.assertFalse(loader.audits[0]['parameter_requires_grad']['backbone.'+A.replace('.lora_A.', '.lora_A.default.')])
        self.assertEqual(self.torch.load_arguments[0][1], {'map_location': 'cpu', 'weights_only': True})
        with self.assertRaisesRegex(ValueError, 'closed'):
            predict({'options': ['a', 'b']})

    def test_four_contexts_are_fresh_and_no_extra_forward(self):
        loader = self.loader()
        for phase in ('calibration', 'heldout'):
            for weight in ('released', 'adapted'):
                with loader(weight, phase):
                    self.assertEqual(self.models[-1].forward_calls, 0)
        self.assertEqual(len(self.models), 4)
        self.assertEqual([(a['weight'], a['phase']) for a in loader.audits],
                         [('released', 'calibration'), ('adapted', 'calibration'),
                          ('released', 'heldout'), ('adapted', 'heldout')])

    def test_owner_loss_before_row_and_exception_cleanup(self):
        valid = True
        def owner():
            if not valid:
                raise RuntimeError('Owner lost')
        with self.assertRaisesRegex(RuntimeError, 'Owner lost'):
            with self.loader(owner=owner)('released', 'calibration') as (_, predict):
                valid = False
                predict({'options': ['a', 'b']})
        self.assertEqual(self.models[-1].forward_calls, 0)
        self.assertEqual(self.torch.cuda.emptied, 1)

    def test_dtype_quantization_env_is_scrubbed_and_restored(self):
        with patch.dict(os.environ, {name: 'unsafe inherited setting' for name in native.JEV_OVERRIDES}):
            with self.loader()('released', 'calibration'):
                self.assertTrue(all(name not in os.environ for name in native.JEV_OVERRIDES))
                self.assertEqual(os.environ['HF_HUB_OFFLINE'], '1')
            self.assertTrue(all(os.environ[name] == 'unsafe inherited setting' for name in native.JEV_OVERRIDES))

    def test_physical_uuid_or_multiple_visible_devices_fail_before_load(self):
        for change in ('uuid', 'count', 'visible', 'cuda'):
            with self.subTest(change=change):
                old = self.torch.cuda.uuid, self.torch.cuda.count, self.bindings['visible_devices'], self.torch.version.cuda
                if change == 'uuid': self.torch.cuda.uuid = UUID.replace('01234567', '99999999')
                if change == 'count': self.torch.cuda.count = 2
                if change == 'visible': self.bindings['visible_devices'] = UUID+',1'
                if change == 'cuda': self.torch.version.cuda = '12.1'
                with self.assertRaises(ValueError):
                    with self.loader()('released', 'calibration'):
                        self.fail('Bad physical runtime entered')
                self.torch.cuda.uuid, self.torch.cuda.count, self.bindings['visible_devices'], self.torch.version.cuda = old
        self.assertEqual(self.models, [])

    def test_source_and_import_location_fail_closed(self):
        def dirty(args, **kwargs):
            return b'?? extra.py' if args[3] == 'status' else self.fake_git(args, **kwargs)
        with patch.object(native.subprocess, 'check_output', side_effect=dirty):
            with self.assertRaisesRegex(ValueError, 'dirty'):
                with self.loader()('released', 'calibration'):
                    pass
        self.assertEqual(self.dependency_calls, 0)
        def shadowed():
            dependencies = self.dependencies()
            dependencies.model_file = str(self.root/'untrusted/jev/model.py')
            return dependencies
        with self.assertRaisesRegex(ValueError, 'import location'):
            with self.loader(dependencies=shadowed)('released', 'calibration'):
                pass
        self.assertEqual(self.models, [])

    def test_checkpoint_fullhash_tampering_precedes_dependencies(self):
        (self.checkpoint/'head.pt').write_text('Changed frozen bytes')
        with self.assertRaisesRegex(ValueError, 'fullhash'):
            with self.loader()('released', 'calibration'):
                pass
        self.assertEqual(self.dependency_calls, 0)

    def test_cached_scientific_dependencies_from_another_root_reject(self):
        for name in ('jev', 'jev.api', 'jev.metrics', 'jev.data', 'jev.prefix_cache'):
            with self.subTest(module=name):
                previous = self.origins[name]
                self.origins[name] = str(self.root/'foreign'/Path(previous).name)
                with self.assertRaisesRegex(ValueError, 'dependency import'):
                    with self.loader()('released', 'calibration'):
                        pass
                self.origins[name] = previous
        self.assertEqual(self.models, [])

    def test_saved_trainable_dtype_cannot_round_into_exact_identity(self):
        self.saved_head['weight'].dtype = 'torch.float64'
        with self.assertRaisesRegex(ValueError, 'dtype/shape'):
            with self.loader()('released', 'calibration'):
                pass

    def test_tensor_value_missing_key_dtype_and_merged_adapter_reject(self):
        original_load = self.model_class.load
        for change in ('value', 'missing', 'dtype', 'merged', 'device'):
            with self.subTest(change=change):
                def changed(path, device='cuda:0'):
                    model = original_load(path, device)
                    if change == 'value': model.parameters['head.weight'].values[0] += 1
                    if change == 'missing': del model.parameters['backbone.base_model.model.embed_tokens.weight']
                    if change == 'dtype': model.parameters['head.weight'].dtype = 'torch.bfloat16'
                    if change == 'merged': model.adapter_module.merged = True
                    if change == 'device': model.parameters['head.bias'].device = 'cpu'
                    return model
                with patch.object(self.model_class, 'load', side_effect=changed):
                    with self.assertRaises(ValueError):
                        with self.loader()('released', 'calibration'):
                            pass
        self.assertEqual(self.torch.cuda.emptied, 5)

    def test_training_original_adamw_first_accumulated_step_zero_bias_and_restoration(self):
        module, args = self.training()
        initialize, adamw = module.initialize_model, self.torch.optim.AdamW
        with native.observe_training(module, self.plan, self.bindings, self.publication, self.base,
            self.scientific, assert_owned=self.assert_owned, dependencies=self.dependencies) as state:
            model = module.initialize_model(args, self.model_class, {})
            optimizer = self.torch.optim.AdamW(['original params'], eps=1e-8)
            self.assertIsNone(state['first_gradient_audit'])
            self.gradients(model, bias=0)
            original_values = {name: p.grad.values[:] for name, p in model.named_parameters() if p.grad is not None}
            for _ in range(733): optimizer.step()
            self.assertEqual(optimizer.steps, 733)
            self.assertEqual(optimizer.args, (['original params'],))
            self.assertEqual(optimizer.kwargs, {'eps': 1e-8})
            self.assertEqual(state['first_gradient_audit']['groups']['head']['zero_parameters'], 1)
            self.assertEqual(state['first_gradient_audit']['groups']['head']['nonzero_parameters'], 1)
            self.assertEqual(original_values, {name: p.grad.values for name, p in model.named_parameters() if p.grad is not None})
            self.assertEqual(model.forward_calls, 0)
        self.assertIs(module.initialize_model, initialize)
        self.assertIs(self.torch.optim.AdamW, adamw)
        self.assertTrue(optimizer.handle.removed)
        self.assertEqual(state['status'], 'training_observer_complete_pending_original_journal_validation')

    def test_none_trainable_gradient_is_reported_without_imputation(self):
        module, args = self.training()
        with native.observe_training(module, self.plan, self.bindings, self.publication, self.base,
            self.scientific, assert_owned=self.assert_owned, dependencies=self.dependencies) as state:
            model = module.initialize_model(args, self.model_class, {})
            self.gradients(model)
            optimizer = self.torch.optim.AdamW([])
            for _ in range(733): optimizer.step()
            audit = state['first_gradient_audit']
            self.assertEqual(audit['groups']['head']['none_parameters'], 1)
            self.assertEqual(audit['trainable_parameters_without_gradient'], 1)
            self.assertIsNone(model.parameters['head.bias'].grad)

    def test_observer_does_not_keep_model_alive_across_original_checkpoint_reload(self):
        module, args = self.training()
        with native.observe_training(module, self.plan, self.bindings, self.publication, self.base,
            self.scientific, assert_owned=self.assert_owned, dependencies=self.dependencies):
            model = module.initialize_model(args, self.model_class, {})
            reference = weakref.ref(model)
            self.gradients(model)
            optimizer = self.torch.optim.AdamW([])
            for _ in range(733): optimizer.step()
            self.models.clear()
            del model
            gc.collect()
            self.assertIsNone(reference(), 'Observer retained the model after the original release')

    def test_nonfinite_zero_group_or_base_grad_fails_before_original_step_and_restores(self):
        for change in ('nonfinite', 'zero_A', 'missing_B', 'base'):
            with self.subTest(change=change):
                module, args = self.training()
                initialize, adamw = module.initialize_model, self.torch.optim.AdamW
                with self.assertRaises(ValueError):
                    with native.observe_training(module, self.plan, self.bindings, self.publication, self.base,
                        self.scientific, assert_owned=self.assert_owned, dependencies=self.dependencies) as state:
                        model = module.initialize_model(args, self.model_class, {})
                        self.gradients(model, bias=0)
                        if change == 'nonfinite': model.parameters['head.bias'].grad.values[0] = float('nan')
                        if change == 'zero_A': model.parameters['backbone.'+A.replace('.lora_A.', '.lora_A.default.')].grad.values = [0]*16
                        if change == 'missing_B': model.parameters['backbone.'+B.replace('.lora_B.', '.lora_B.default.')].grad = None
                        if change == 'base': model.parameters['backbone.base_model.model.embed_tokens.weight'].grad = FakeTensor([1]*4)
                        optimizer = self.torch.optim.AdamW([])
                        optimizer.step()
                self.assertEqual(optimizer.steps, 0)
                self.assertIs(module.initialize_model, initialize)
                self.assertIs(self.torch.optim.AdamW, adamw)
                self.assertTrue(optimizer.handle.removed)
                self.assertEqual(state['status'], 'training_observer_failed')

    def test_incomplete_training_or_changed_settings_do_not_report_success(self):
        module, args = self.training()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            with native.observe_training(module, self.plan, self.bindings, self.publication, self.base,
                self.scientific, assert_owned=self.assert_owned, dependencies=self.dependencies):
                model = module.initialize_model(args, self.model_class, {})
                self.gradients(model)
                self.torch.optim.AdamW([]).step()
        args.accumulation = 1
        with self.assertRaisesRegex(ValueError, 'arguments'):
            with native.observe_training(module, self.plan, self.bindings, self.publication, self.base,
                self.scientific, assert_owned=self.assert_owned, dependencies=self.dependencies):
                module.initialize_model(args, self.model_class, {})


if __name__ == '__main__':
    unittest.main()
