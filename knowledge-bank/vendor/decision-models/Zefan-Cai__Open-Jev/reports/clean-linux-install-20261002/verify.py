from pathlib import Path
import hashlib
import importlib
import importlib.metadata as md
import importlib.resources as resources
import json
import os
import platform
import site
import sys
import sysconfig

root = Path.cwd()
assert os.environ['CUDA_VISIBLE_DEVICES'] == ''
assert 'PYTHONPATH' not in os.environ
assert sys.prefix != sys.base_prefix
assert site.ENABLE_USER_SITE is False
config = (Path(sys.prefix) / 'pyvenv.cfg').read_text()
assert 'include-system-site-packages = false' in config
import torch
assert not torch.cuda.is_initialized()

def forbidden_cuda_init(*args, **kwargs):
    raise RuntimeError('CUDA initialization is forbidden in this CPU reproduction')

torch.cuda._lazy_init = forbidden_cuda_init
expected = torch.tensor([[7., 10.], [15., 22.]])
assert torch.equal(torch.tensor([[1., 2.], [3., 4.]]) @ torch.tensor([[1., 2.], [3., 4.]]), expected)
modules = ['jev.server', 'jev.fast_backend', 'jev.kernels.final_score', 'transformers', 'peft', 'accelerate', 'datasets', 'triton', 'ninja', 'safetensors', 'fla.ops.gated_delta_rule', 'fla.ops.gated_delta_rule.chunk_fwd', 'fla.ops.common.chunk_delta_h', 'fla.ops.common.chunk_o', 'fla.ops.gated_delta_rule.wy_fast', 'fla.ops.utils.constant']
imports = {}
for name in modules:
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(Path(sys.prefix).resolve()), (name, path)
    imports[name] = str(path.relative_to(Path(sys.prefix).resolve()))
symbols = {
    'fla.ops.gated_delta_rule': ['chunk_gated_delta_rule'],
    'fla.ops.utils': ['chunk_local_cumsum'],
    'fla.ops.utils.constant': ['RCP_LN2'],
    'fla.ops.gated_delta_rule.chunk_fwd': ['chunk_gated_delta_rule_fwd_intra', 'chunk_gated_delta_rule_fwd_kkt_solve_kernel'],
    'fla.ops.common.chunk_delta_h': ['chunk_gated_delta_rule_fwd_h'],
    'fla.ops.common.chunk_o': ['chunk_fwd_o'],
    'fla.ops.gated_delta_rule.wy_fast': ['recompute_w_u_fwd'],
}
for name, required in symbols.items():
    module = importlib.import_module(name)
    assert all(hasattr(module, symbol) for symbol in required), name
from jev.kernels.final_score import reference_final_rms_head
hidden = torch.tensor([[1., -1.], [0., 0.]])
score = reference_final_rms_head(hidden, torch.tensor([0, 1]), torch.zeros(2), torch.tensor([0.5, -0.5]), torch.tensor([0.25]))
assert torch.allclose(score, torch.tensor([1.2499995, 0.25]), rtol=0, atol=1e-6)
files = {}
for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'PROVENANCE.json', 'src/kernels.cu', 'src/lt.cpp', 'src/ext.py', 'src/fastmodel.py']:
    value = resources.files('third_party.open_jev_fast').joinpath(name).read_bytes()
    assert value
    files[name] = {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
installed = []
for dist in sorted(md.distributions(), key=lambda d: d.metadata['Name'].lower()):
    path = Path(dist.locate_file('')).resolve()
    assert path.is_relative_to(Path(sys.prefix).resolve()), (dist.metadata['Name'], path)
    installed.append({'name': dist.metadata['Name'], 'version': dist.version, 'location': str(path.relative_to(Path(sys.prefix).resolve()))})
receipt = {'status': 'passed', 'python': platform.python_version(), 'platform': platform.platform(), 'torch': torch.__version__, 'torch_build_cuda': torch.version.cuda, 'cuda_visible_devices': '', 'cuda_initialized': torch.cuda.is_initialized(), 'cpu_matrix_check': 'passed', 'cpu_reference_score_check': 'passed', 'system_site_packages': False, 'user_site_enabled': site.ENABLE_USER_SITE, 'pythonpath_present': False, 'sys_prefix_matches_base': sys.prefix == sys.base_prefix, 'base_prefix_sha256': hashlib.sha256(sys.base_prefix.encode()).hexdigest(), 'imports': imports, 'required_fla_symbols': symbols, 'wheel_resources': files, 'distributions': installed, 'model_weights_loaded': False, 'kernel_execution_verified': False}
assert receipt['cuda_initialized'] is False
(root / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
