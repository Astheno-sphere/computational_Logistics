"""Hash-bound release-package initialization for a new training run.

Metadata validation is CPU-only and imports no model runtime. Inference packages
are weights-only sources, never optimizer/RNG/cursor resume checkpoints.
"""
import json
import math
from pathlib import Path, PurePosixPath
import re

from .train import _file_sha256, _json_sha256


CHECKPOINT_FILES = {"checkpoint/model.json", "checkpoint/head.pt", "checkpoint/temperature.json",
                    "checkpoint/adapter/adapter_config.json", "checkpoint/adapter/adapter_model.safetensors"}
RESET_FIELDS = {"kind": "inference_package_weights_only", "optimizer": "new_adamw_state",
                "rng": "new_run_seed_and_rank_streams", "step_cursor": 0,
                "baseline_initialization": "warm_start_checkpoint", "temperature": "refit_on_new_calibration"}
PROVENANCE_HASHES = {"source_manifest_sha256", "source_checkpoint_sha256", "source_training_identity_sha256",
                     "source_provenance_sha256", "source_temperature_sha256"}


def validate_inference_initialization_provenance(value):
    if (not isinstance(value, dict) or set(value) != set(RESET_FIELDS) | PROVENANCE_HASHES | {"source_completed_step"}
            or any(value.get(k) != v or type(value.get(k)) is not type(v) for k, v in RESET_FIELDS.items())
            or type(value.get("source_completed_step")) is not int or value["source_completed_step"] < 1
            or any(not isinstance(value.get(k), str) or not re.fullmatch(r"[0-9a-f]{64}", value[k]) for k in PROVENANCE_HASHES)):
        raise ValueError("Invalid inference-package initialization provenance")
    return value


def read_inference_initialization_package(path, expected_manifest_sha256, model, revision, lora_rank):
    """Verify the complete pinned package before importing Torch or loading weights."""
    path = Path(path)
    if (not isinstance(expected_manifest_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256)
            or path.is_symlink() or not path.is_dir() or (path / "manifest.json").is_symlink()
            or not (path / "manifest.json").is_file()
            or _file_sha256(path / "manifest.json") != expected_manifest_sha256):
        raise ValueError("Initialization package manifest differs from the required SHA256")
    manifest = json.loads((path / "manifest.json").read_text())
    if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int
            or manifest.get("schema_version") != 1 or manifest.get("kind") != "local_inference_weight_package"
            or manifest.get("model") != model or manifest.get("revision") != revision):
        raise ValueError("Initialization package type/model/revision differs")
    files = manifest.get("files")
    if not isinstance(files, dict) or not CHECKPOINT_FILES | {"provenance.json"} <= set(files):
        raise ValueError("Initialization package lacks required inference files")
    actual = set()
    for entry in path.rglob("*"):
        if entry.is_symlink():
            raise ValueError("Symlinks are forbidden in initialization packages")
        if entry.is_file():
            actual.add(entry.relative_to(path).as_posix())
        elif not entry.is_dir():
            raise ValueError("Nonregular initialization package entry")
    if actual != set(files) | {"manifest.json"}:
        raise ValueError("Initialization package contains missing or unlisted files")
    for name, record in files.items():
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or str(relative) != name
                or not isinstance(record, dict) or set(record) != {"sha256", "bytes"}
                or type(record.get("bytes")) is not int or record["bytes"] < 0
                or not isinstance(record.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
                or (path / name).stat().st_size != record["bytes"]
                or _file_sha256(path / name) != record["sha256"]):
            raise ValueError("Initialization package file checksum/size/path differs: " + name)
    if {name for name in files if name.startswith("checkpoint/")} != CHECKPOINT_FILES:
        raise ValueError("Initialization supports only the complete safetensors LoRA/head checkpoint")
    config = json.loads((path / "checkpoint/model.json").read_text())
    adapter = json.loads((path / "checkpoint/adapter/adapter_config.json").read_text())
    previous = json.loads((path / "provenance.json").read_text())
    temperature = json.loads((path / "checkpoint/temperature.json").read_text())
    if (type(lora_rank) is not int or lora_rank < 1
            or config.get("model_id") != model or config.get("revision") != revision
            or type(config.get("lora_rank")) is not int or config["lora_rank"] != lora_rank
            or config.get("method") != "independent_candidate_lora_nll_brier"
            or adapter.get("peft_type") != "LORA" or type(adapter.get("r")) is not int or adapter["r"] != lora_rank
            or previous.get("model") != model or previous.get("revision") != revision
            or previous.get("training", {}).get("lora_rank") != lora_rank):
        raise ValueError("Initialization checkpoint model/revision/LoRA configuration differs")
    if (type(temperature.get("temperature")) not in (int, float) or not math.isfinite(temperature["temperature"])
            or temperature["temperature"] <= 0 or temperature.get("split") != "calibration"):
        raise ValueError("Source inference calibration is invalid")
    training = previous.get("training", {})
    provenance = {**RESET_FIELDS, "source_manifest_sha256": expected_manifest_sha256,
                  "source_checkpoint_sha256": _json_sha256({k: files[k] for k in sorted(CHECKPOINT_FILES)}),
                  "source_training_identity_sha256": training.get("run_identity_sha256"),
                  "source_completed_step": training.get("steps"),
                  "source_provenance_sha256": files["provenance.json"]["sha256"],
                  "source_temperature_sha256": files["checkpoint/temperature.json"]["sha256"]}
    return {"manifest": manifest, "config": config, "adapter_config": adapter}, validate_inference_initialization_provenance(provenance)


def initialize_inference_weights(model, path, metadata, provenance):
    """Validate all saved tensors, then copy only existing trainable LoRA/head tensors."""
    import torch
    from safetensors.torch import load_file
    validate_inference_initialization_provenance(provenance)
    current, bound = read_inference_initialization_package(
        path, provenance["source_manifest_sha256"], model.model_id, model.revision, model.lora_rank)
    if current != metadata or bound != provenance:
        raise ValueError("Initialization package/provenance changed after preflight")
    adapter_config = metadata["adapter_config"]
    expected_config = model.backbone.peft_config["default"]
    for key in ("r", "lora_alpha", "lora_dropout", "bias", "fan_in_fan_out", "use_dora", "use_rslora",
                "rank_pattern", "alpha_pattern", "modules_to_save", "layers_to_transform", "layers_pattern",
                "layer_replication", "target_parameters", "lora_bias"):
        if adapter_config.get(key) != getattr(expected_config, key, None):
            raise ValueError("Source LoRA settings differ from the new training model: " + key)
    if set(adapter_config.get("target_modules", [])) != set(expected_config.target_modules):
        raise ValueError("Source LoRA target modules differ from the new training model")
    parameters = {}
    for name, parameter in model.backbone.named_parameters():
        if parameter.requires_grad:
            if not re.search(r"\.lora_[AB]\.default\.weight$", name):
                raise ValueError("Unsupported trainable adapter parameter: " + name)
            key = name.replace(".default.", ".")
            if key in parameters:
                raise ValueError("Ambiguous adapter parameter mapping")
            parameters[key] = parameter
    head = dict(model.head.named_parameters())
    if not parameters or set(head) != {"weight", "bias"} or any(not p.requires_grad for p in head.values()):
        raise ValueError("Initialization requires trainable LoRA and scalar head parameters")
    saved_adapter = load_file(str(Path(path) / "checkpoint/adapter/adapter_model.safetensors"), device="cpu")
    saved_head = torch.load(Path(path) / "checkpoint/head.pt", map_location="cpu", weights_only=True)
    for label, live, saved in (("adapter", parameters, saved_adapter), ("head", head, saved_head)):
        if not isinstance(saved, dict) or set(live) != set(saved):
            raise ValueError("Initialization " + label + " parameter names differ")
        for name, parameter in live.items():
            value = saved[name]
            if (not isinstance(value, torch.Tensor) or value.shape != parameter.shape or value.dtype != parameter.dtype
                    or not torch.isfinite(value).all()):
                raise ValueError("Initialization parameter shape/dtype/value differs: " + name)
    # Bind both file reads once more before any tensor is copied. The package is
    # immutable input; training outputs and calibration are written elsewhere.
    if read_inference_initialization_package(path, provenance["source_manifest_sha256"],
                                            model.model_id, model.revision, model.lora_rank) != (metadata, provenance):
        raise ValueError("Initialization package changed while loading tensors")
    with torch.no_grad():
        for live, saved in ((parameters, saved_adapter), (head, saved_head)):
            for name, parameter in live.items():
                parameter.copy_(saved[name])
    return provenance
