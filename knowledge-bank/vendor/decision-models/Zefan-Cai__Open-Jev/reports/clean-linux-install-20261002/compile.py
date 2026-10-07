from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import os
import time
import traceback
import torch
from torch.utils.cpp_extension import _get_build_directory, load_inline
import third_party.open_jev_fast

root = Path.cwd()
assert os.environ['CUDA_VISIBLE_DEVICES'] == ''
assert os.environ['TORCH_CUDA_ARCH_LIST'] == '9.0'
assert not torch.cuda.is_initialized()

def forbidden_cuda_init(*args, **kwargs):
    raise RuntimeError('CUDA initialization is forbidden in this compilation-only check')

torch.cuda._lazy_init = forbidden_cuda_init
source = Path(third_party.open_jev_fast.__file__).parent / 'src/ext.py'
spec = importlib.util.spec_from_file_location('openjev_compile_definition', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
call = next(node for node in ast.walk(ast.parse(source.read_text())) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'load_inline')
kwargs = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords if keyword.arg in ('functions', 'extra_cuda_cflags')}
cuda_source = source.parent / 'kernels.cu'
started = time.monotonic()
try:
    name = 'openjev_clean_linux_sm90'
    extension = load_inline(name=name, cpp_sources=[module._CPP], cuda_sources=[cuda_source.read_text()], build_directory=_get_build_directory(name, True), verbose=True, **kwargs)
    artifact = Path(extension.__file__)
    receipt = {'status': 'compiled_and_loaded_without_gpu_execution', 'sm_target': '90', 'max_jobs': 2, 'cuda_visible_devices': '', 'torch': torch.__version__, 'extension_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(), 'extension_file': str(artifact.relative_to(root)), 'source_files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, cuda_source)}, 'seconds': time.monotonic() - started, 'cuda_initialized': torch.cuda.is_initialized(), 'kernel_execution_verified': False, 'full_model_parity_verified': False}
    assert receipt['cuda_initialized'] is False
except Exception as error:
    traceback.print_exc()
    receipt = {'status': 'failed', 'error_type': type(error).__name__, 'error': str(error), 'seconds': time.monotonic() - started, 'cuda_initialized': torch.cuda.is_initialized(), 'kernel_execution_verified': False}
(root / 'compilation.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
if receipt['status'] == 'failed':
    raise SystemExit(2)
