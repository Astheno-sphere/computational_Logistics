"""Launch a bounded three-model pilot only on GPUs with no compute process."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
MODELS = [
    (0, "2b", "Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    (1, "9b", "Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    (2, "27b", "Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
]


def main():
    python = "/mnt/localssd/jev-qwen/doom-venv/bin/python"
    gpu_rows = subprocess.check_output([
        "nvidia-smi", "--query-gpu=index,uuid,memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True)
    active = subprocess.check_output([
        "nvidia-smi", "--query-compute-apps=gpu_uuid", "--format=csv,noheader"], text=True).splitlines()
    free = {}
    for line in gpu_rows.splitlines():
        index, uuid, memory, utilization = [part.strip() for part in line.split(",")]
        free[int(index)] = uuid not in active and int(memory) < 512 and int(utilization) < 10
    if not all(free[gpu] for gpu, *_ in MODELS):
        raise RuntimeError("Requested pilot GPUs are not all free; no processes were started")
    work = WORK / "runs"
    work.mkdir(exist_ok=True)
    handles = []
    for gpu, tag, model, revision in MODELS:
        output = work / f"{tag}-pilot-v1"
        if output.exists():
            raise RuntimeError(f"Refusing to overwrite an existing run: {output}")
    for gpu, tag, model, revision in MODELS:
        output = work / f"{tag}-pilot-v1"
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), HF_HUB_CACHE="/mnt/localssd/jev-hf-cache",
                   HF_HUB_OFFLINE="1", OMP_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false")
        log = open(work / f"{tag}-pilot-v1.log", "w")
        command = [python, "-u", "-m", "jev.train", "--model", model, "--revision", revision,
                   "--data", str(ROOT / "data/cases-pilot"), "--output", str(output),
                   "--steps", "100", "--max-length", "1536"]
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        log.close()
        handles.append({"gpu": gpu, "tag": tag, "pid": process.pid, "command": command,
                        "output": str(output), "log": str(work / f"{tag}-pilot-v1.log")})
    (work / "launch.json").write_text(json.dumps(handles, indent=2) + "\n")
    print(json.dumps(handles, indent=2))


if __name__ == "__main__":
    main()
