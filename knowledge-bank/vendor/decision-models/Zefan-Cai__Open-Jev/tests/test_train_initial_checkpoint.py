import argparse
import builtins
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jev import train


class Parameter:
    def __init__(self):
        self.requires_grad = True

    def requires_grad_(self, enabled):
        self.requires_grad = enabled


class FrozenInferenceModel:
    def __init__(self):
        self.parameters = {name: Parameter() for name in (
            'head.weight', 'head.bias', 'backbone.q.lora_A.default.weight',
            'backbone.q.lora_B.default.weight', 'backbone.q.base_layer.weight')}
        self.backbone = Mock()

    def requires_grad_(self, enabled):
        for parameter in self.parameters.values():
            parameter.requires_grad_(enabled)

    def named_parameters(self):
        return self.parameters.items()


class InitialInferenceCheckpointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkpoint = self.root/'released'
        (self.checkpoint/'adapter').mkdir(parents=True)
        self.config = dict(model_id='Qwen/tiny', revision='a'*40, lora_rank=8, max_length=4096,
                           method='independent_candidate_lora_nll_brier')
        (self.checkpoint/'model.json').write_text(json.dumps(self.config))
        (self.checkpoint/'temperature.json').write_text(json.dumps({'temperature':1.5}))
        self.adapter = dict(peft_type='LORA',r=8,base_model_name_or_path='',revision=None,rank_pattern={})
        (self.checkpoint/'adapter/adapter_config.json').write_text(json.dumps(self.adapter))
        (self.checkpoint/'adapter/adapter_model.safetensors').write_bytes(b'fixture-adapter')
        (self.checkpoint/'head.pt').write_bytes(b'fixture-head')
        self.args = argparse.Namespace(initial_checkpoint=str(self.checkpoint), resume_training=None,
            model='Qwen/tiny', revision='a'*40, lora_rank=8, max_length=4096, steps=3,
            train_rows=12, calibration_rows=4, eval_rows=4, accumulation=4,
            lr=2e-5, head_lr=5e-5, brier_weight=.1, seed=20261002,checkpoint_every=0,
            output=str(self.root/'training'))

    def test_loads_existing_weights_and_unfreezes_only_lora_and_head(self):
        identity = train.initial_checkpoint_identity(self.args)
        factory = Mock()
        model = FrozenInferenceModel()
        factory.load.return_value = model
        self.assertIs(train.initialize_model(self.args, factory, identity), model)
        factory.assert_not_called()
        factory.load.assert_called_once_with(str(self.checkpoint))
        for name, parameter in model.parameters.items():
            self.assertEqual(parameter.requires_grad, name != 'backbone.q.base_layer.weight')
        model.backbone.gradient_checkpointing_enable.assert_called_once_with()
        model.backbone.enable_input_require_grads.assert_called_once_with()

    def test_default_base_constructor_is_unchanged(self):
        self.args.initial_checkpoint = None
        self.assertIsNone(train.initial_checkpoint_identity(self.args))
        factory = Mock()
        self.assertIs(train.initialize_model(self.args, factory, None), factory.return_value)
        factory.assert_called_once_with('Qwen/tiny', 'a'*40, lora_rank=8, max_length=4096)
        factory.load.assert_not_called()

    def test_profile_mismatches_and_resume_reject_before_model_import(self):
        original_import = builtins.__import__
        def guarded_import(name, *args, **kwargs):
            if name.split('.')[0] in ('torch','transformers','peft') or name in ('jev.model','model'):
                raise AssertionError('Model dependency imported during rejected preflight')
            return original_import(name,*args,**kwargs)
        for field, value in (('model','other'),('revision','b'*40),('lora_rank',16),
                             ('max_length',8192),('resume_training','old-snapshot'),('checkpoint_every',1),
                             ('output',str(self.checkpoint)),('output',str(self.root)),
                             ('output',str(self.checkpoint/'nested-training'))):
            args = copy.copy(self.args)
            setattr(args,field,value)
            with self.subTest(field=field), patch.object(train,'source_checkout_commit',return_value='c'*40), \
                    patch('builtins.__import__',side_effect=guarded_import), self.assertRaises(ValueError):
                train.run(args)

    def test_actual_adapter_configuration_and_method_must_agree(self):
        path = self.checkpoint/'adapter/adapter_config.json'
        for field,value in (('r',16),('r',True),('peft_type','OTHER'),
                            ('base_model_name_or_path','Qwen/other'),('revision','b'*40),
                            ('rank_pattern',{'q_proj':16})):
            path.write_text(json.dumps({**self.adapter,field:value}))
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Initial adapter'):
                train.initial_checkpoint_identity(self.args)
        path.write_text(json.dumps(self.adapter))
        (self.checkpoint/'model.json').write_text(json.dumps({**self.config,'method':'other'}))
        with self.assertRaisesRegex(ValueError,'Initial adapter'):
            train.initial_checkpoint_identity(self.args)

    def test_content_identity_binds_initialization_and_detects_changed_weights(self):
        initial = train.initial_checkpoint_identity(self.args)
        default = train.training_identity(self.args, {'train':'data'}, {'train':[{'id':'row'}]}, {})
        initialized = train.training_identity(self.args, {'train':'data'}, {'train':[{'id':'row'}]}, {}, initial)
        self.assertNotIn('initial_checkpoint',default)
        self.assertEqual(initialized['initial_checkpoint'],initial)
        self.assertEqual(len(initial['files_sha256']),5)
        (self.checkpoint/'head.pt').write_bytes(b'changed-head')
        factory = Mock()
        with self.assertRaisesRegex(ValueError,'changed after preflight'):
            train.initialize_model(self.args,factory,initial)
        factory.load.assert_not_called()
        self.assertNotEqual(initial,train.initial_checkpoint_identity(self.args))

    def test_missing_serving_files_and_invalid_temperature_are_rejected(self):
        (self.checkpoint/'temperature.json').write_text('{"temperature": 0}')
        with self.assertRaisesRegex(ValueError,'temperature'):
            train.initial_checkpoint_identity(self.args)
        (self.checkpoint/'temperature.json').write_text('{"temperature": 1.5}')
        (self.checkpoint/'head.pt').unlink()
        with self.assertRaisesRegex(ValueError,'requires config'):
            train.initial_checkpoint_identity(self.args)


if __name__ == '__main__':
    unittest.main()
