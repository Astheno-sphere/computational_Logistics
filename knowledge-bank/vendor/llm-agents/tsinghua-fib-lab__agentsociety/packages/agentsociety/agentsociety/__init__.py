"""
agentsociety: City agent building framework
"""

import os
import requests

from .logger import get_logger


# huggingface连通性检测与国内源切换
def _check_hf_connectivity():
    try:
        resp = requests.get("https://huggingface.co", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


hf_envs = ["HF_ENDPOINT", "HF_HUB_ENDPOINT"]
hf_env_set = any(os.environ.get(e) for e in hf_envs)
if not _check_hf_connectivity() and not hf_env_set:
    # 切换为国内源
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    os.environ["HF_HUB_ENDPOINT"] = "https://hf-mirror.com"
    get_logger().warning(
        "Huggingface无法连通，已自动切换为国内源 https://hf-mirror.com"
    )
