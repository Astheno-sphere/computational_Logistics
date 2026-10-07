import os
import platform
import stat
import requests
from ..logger import get_logger

__all__ = ["download_binary"]

SIM_VERSION = "v0.2.2"
BIN_SOURCES = {
    "agentsociety-sim-oss": {
        "linux_x86_64": f"https://tsinghua-agentsociety.oss-cn-beijing.aliyuncs.com/agentsociety-sim-oss/{SIM_VERSION}/agentsociety-sim-oss-linux-amd64",
        "darwin_arm64": f"https://tsinghua-agentsociety.oss-cn-beijing.aliyuncs.com/agentsociety-sim-oss/{SIM_VERSION}/agentsociety-sim-oss-darwin-arm64",
    },
}


def download_binary(home_dir: str) -> str:
    binary_name = "agentsociety-sim-oss"
    bin_path = os.path.join(home_dir, binary_name)
    if os.path.exists(bin_path):
        return bin_path

    system = platform.system()
    machine = platform.machine()

    if system == "Linux":
        plat_dir = "linux"
        if machine == "x86_64":
            arch = "x86_64"
        else:
            raise Exception("agentsociety-sim-oss: Unsupported architecture on Linux. Only x86_64 is supported.")
    elif system == "Darwin" and machine.startswith("arm"):
        plat_dir = "darwin"
        arch = "arm64"
    else:
        raise Exception("agentsociety-sim-oss: Unsupported platform. Only Linux x86_64 and Darwin (macOS) arm64 are supported.")

    url = BIN_SOURCES[binary_name].get(f"{plat_dir}_{arch}")
    if not url:
        raise Exception(f"No binary found for {binary_name}")

    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Download failed for {binary_name}")

    bin_path = os.path.abspath(bin_path)

    with open(bin_path, "wb") as f:
        f.write(response.content)
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    get_logger().info(msg=f"Downloaded {binary_name} to {bin_path}")
    return bin_path
