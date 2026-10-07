"""Shard the frozen base while keeping checkpoint-compatible LoRA/head tensors.

Every forward requires participation from all four ranks. Only the small,
replicated trainable state can be saved by rank zero without collectives.
"""
import json
from pathlib import Path


WORLD_SIZE = 4


def _decoder_layers(model):
    backbone = model.backbone.get_base_model()
    layers = getattr(backbone, "layers", None)
    if layers is None or not len(layers):
        raise ValueError("Frozen-base sharding requires an explicit decoder layer sequence")
    return list(layers)


def replicated_parameters(model):
    """Canonical names and ordinary FP32 Parameters, also used by old snapshots."""
    import torch
    from torch.distributed.tensor import DTensor
    parameters = {name: parameter for name, parameter in model.named_parameters() if parameter.requires_grad}
    if not parameters:
        raise ValueError("Replicated LoRA/head parameters are missing")
    for name, parameter in parameters.items():
        if isinstance(parameter, DTensor) or parameter.dtype != torch.float32:
            raise ValueError("Trainable parameters must remain ordinary FP32 tensors: " + name)
        if not (name.startswith("head.") or ".lora_A.default.weight" in name or ".lora_B.default.weight" in name):
            raise ValueError("Unexpected trainable parameter: " + name)
    return parameters


def frozen_shard_plan(model):
    """CPU metadata estimate; it does not claim a measured CUDA peak."""
    layers = _decoder_layers(model)
    trainable = replicated_parameters(model)
    layer_parameter_ids = set()
    layer_bytes = []
    for layer in layers:
        amount = 0
        for parameter in layer.parameters():
            if not parameter.requires_grad:
                if id(parameter) in layer_parameter_ids:
                    raise ValueError("Frozen parameters shared across decoder layers are unsupported")
                layer_parameter_ids.add(id(parameter))
                amount += parameter.numel() * parameter.element_size()
        if amount == 0:
            raise ValueError("Each decoder layer must contain frozen base tensors")
        layer_bytes.append(amount)
    frozen_bytes = sum(p.numel() * p.element_size() for p in model.parameters() if not p.requires_grad)
    root_bytes = frozen_bytes - sum(layer_bytes)
    if root_bytes < 0:
        raise ValueError("Frozen parameter ownership is inconsistent")
    return {"world_size": WORLD_SIZE, "decoder_layers": len(layers), "frozen_parameter_bytes": frozen_bytes,
            "replicated_trainable_bytes": sum(p.numel() * p.element_size() for p in trainable.values()),
            "frozen_layer_bytes": layer_bytes, "frozen_root_bytes": root_bytes,
            "estimated_frozen_shard_bytes_per_rank": (frozen_bytes + WORLD_SIZE - 1) // WORLD_SIZE,
            "largest_unsharded_unit_bytes": max([root_bytes, *layer_bytes]),
            "reshard_after_forward": True, "training_gradient_reduction": "sum/4 over replicated trainables",
            "limitations": "Weight bytes only; all-gather buffers, activations, kernels and allocator reserve require a bounded runtime measurement"}


def shard_frozen_base(model, device, mesh=None):
    """Mutate a CPU-loaded DecisionModel; caller must set memory limits first.

    FSDP2's ignored_params are neither moved nor reduced automatically. Keeping
    them replicated preserves the existing optimizer order and snapshot format.
    """
    import torch
    import torch.distributed as dist
    from torch.distributed.device_mesh import init_device_mesh
    from torch.distributed.fsdp import fully_shard
    from torch.distributed.tensor import DTensor

    device = torch.device(device)
    if not dist.is_initialized() or dist.get_world_size() != WORLD_SIZE:
        raise ValueError("Frozen-base sharding requires an initialized four-rank process group")
    if device.type not in ("cuda", "cpu"):
        raise ValueError("Only CUDA training and CPU fixtures are supported")
    if device.type == "cuda" and device.index != dist.get_rank():
        raise ValueError("The four local CUDA devices must map directly to ranks zero through three")
    if any(p.device.type != "cpu" for p in model.parameters()) or any(b.device.type != "cpu" for b in model.buffers()):
        raise ValueError("Construct the complete model on CPU before frozen-base sharding")
    plan = frozen_shard_plan(model)
    original = replicated_parameters(model)
    if any(p.grad is not None for p in original.values()):
        raise ValueError("Shard the model before creating a training graph")
    layers = _decoder_layers(model)
    mesh = init_device_mesh(device.type, (WORLD_SIZE,)) if mesh is None else mesh
    if mesh.device_type != device.type or mesh.ndim != 1 or mesh.size() != WORLD_SIZE:
        raise ValueError("Frozen-base sharding requires a one-dimensional four-rank device mesh")
    # Do not call model.to(device): the full BF16 base does not fit the budget.
    with torch.no_grad():
        for parameter in original.values():
            parameter.data = parameter.data.to(device)
    ignored = set(original.values())
    for layer in layers:
        fully_shard(layer, mesh=mesh, ignored_params=ignored, reshard_after_forward=True)
    fully_shard(model, mesh=mesh, ignored_params=ignored, reshard_after_forward=True)
    model.device_name = str(device)
    current = replicated_parameters(model)
    if set(current) != set(original) or any(current[name] is not parameter for name, parameter in original.items()):
        raise ValueError("Sharding changed replicated trainable identities or canonical names")
    if any(p.device != device for p in current.values()):
        raise ValueError("An ignored trainable parameter was not moved to its local device")
    if any(not isinstance(p, DTensor) for p in model.parameters() if not p.requires_grad):
        raise ValueError("A frozen base tensor remained replicated")
    model.frozen_shard_metadata = plan
    return model


def replicated_gradient_step(model, optimizer, row, brier_weight, clip_norm=1.0):
    """One row per rank; average gradients once, then clip and update AdamW."""
    import torch
    import torch.distributed as dist
    if not dist.is_initialized() or dist.get_world_size() != WORLD_SIZE:
        raise ValueError("Replicated gradients require exactly four ranks")
    parameters = list(replicated_parameters(model).values())
    optimizer.zero_grad(set_to_none=True)
    logits = model([row])[0].float()
    target = torch.tensor(row["target"], device=logits.device)
    loss = -(target * logits.log_softmax(-1)).sum() + brier_weight * ((logits.softmax(-1) - target) ** 2).sum()
    finite = torch.isfinite(loss).to(dtype=torch.int32)
    dist.all_reduce(finite, op=dist.ReduceOp.MIN)
    if not finite.item():
        raise FloatingPointError("Nonfinite loss on a rank; no optimizer step performed")
    loss.backward()
    complete = torch.tensor(int(all(p.grad is not None for p in parameters)), dtype=torch.int32, device=logits.device)
    dist.all_reduce(complete, op=dist.ReduceOp.MIN)
    if not complete.item():
        raise ValueError("A trainable gradient is absent on a rank; no optimizer step performed")
    # ~60 MiB for 27B LoRA/head: one collective avoids hundreds of tiny calls.
    gradient = torch.cat([p.grad.reshape(-1) for p in parameters])
    dist.all_reduce(gradient)
    gradient.div_(WORLD_SIZE)
    offset = 0
    for parameter in parameters:
        size = parameter.numel()
        parameter.grad.copy_(gradient[offset:offset + size].view_as(parameter))
        offset += size
    del gradient
    norm = torch.nn.utils.clip_grad_norm_(parameters, clip_norm)
    finite = torch.isfinite(norm).to(dtype=torch.int32)
    dist.all_reduce(finite, op=dist.ReduceOp.MIN)
    if not finite.item():
        raise FloatingPointError("Nonfinite synchronized gradient; no optimizer step performed")
    optimizer.step()
    mean_loss = loss.detach()
    dist.all_reduce(mean_loss)
    return mean_loss.item() / WORLD_SIZE, norm.item()


def trainable_state_cpu(model):
    """Collect only replicated trainables; never gather frozen base tensors."""
    import torch
    state = {}
    for name, parameter in replicated_parameters(model).items():
        value = parameter.detach().cpu().clone()
        if not torch.isfinite(value).all():
            raise ValueError("Cannot save a nonfinite trainable tensor: " + name)
        state[name] = value
    return state


def save_replicated_checkpoint(model, output):
    """Rank-zero-safe adapter/head export; temperature is fitted separately."""
    import torch
    state = trainable_state_cpu(model)
    backbone = {name.removeprefix("backbone."): value for name, value in state.items() if name.startswith("backbone.")}
    head = {name.removeprefix("head."): value for name, value in state.items() if name.startswith("head.")}
    if set(head) != {"weight", "bias"} or not backbone:
        raise ValueError("Complete LoRA and scalar-head weights are required")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Checkpoint output must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    # Explicit state_dict prevents PEFT from walking/gathering the frozen base.
    model.backbone.save_pretrained(output / "adapter", state_dict=backbone, safe_serialization=True,
                                   save_embedding_layers=False)
    torch.save(head, output / "head.pt")
    (output / "model.json").write_text(json.dumps({
        "model_id": model.model_id, "revision": model.revision,
        "max_length": model.max_length, "lora_rank": model.lora_rank,
        "method": "independent_candidate_lora_nll_brier"}, indent=2) + "\n")


def reload_replicated_checkpoint(model, output):
    """Reload only validated adapter/head tensors into the existing pinned base.

    This is not a fresh base-model reload. No frozen tensor or optimizer state
    is read or gathered, and validation finishes before any parameter changes.
    """
    import torch
    from safetensors.torch import load_file
    output = Path(output)
    for name in ("model.json", "head.pt", "adapter/adapter_config.json", "adapter/adapter_model.safetensors"):
        path = output / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Reload requires regular checkpoint files: " + name)
    config = json.loads((output / "model.json").read_text())
    if (not isinstance(config, dict) or config.get("model_id") != model.model_id or config.get("revision") != model.revision
            or type(config.get("lora_rank")) is not int or config["lora_rank"] != model.lora_rank
            or type(config.get("max_length")) is not int or config["max_length"] < 1
            or config.get("method") != "independent_candidate_lora_nll_brier"):
        raise ValueError("Checkpoint model identity or configuration differs")
    saved_config = json.loads((output / "adapter/adapter_config.json").read_text())
    live_config = model.backbone.peft_config["default"]
    if not isinstance(saved_config, dict) or saved_config.get("peft_type") != "LORA":
        raise ValueError("Checkpoint is not a supported LoRA adapter")
    for key in ("r", "lora_alpha", "lora_dropout", "bias", "fan_in_fan_out", "use_dora", "use_rslora",
                "rank_pattern", "alpha_pattern", "modules_to_save", "layers_to_transform", "layers_pattern",
                "layer_replication", "target_parameters", "lora_bias"):
        if saved_config.get(key) != getattr(live_config, key, None):
            raise ValueError("Checkpoint LoRA settings differ: " + key)
    if set(saved_config.get("target_modules", [])) != set(live_config.target_modules):
        raise ValueError("Checkpoint LoRA target modules differ")
    live_adapter, live_head = {}, {}
    for name, parameter in replicated_parameters(model).items():
        if name.startswith("backbone."):
            key = name.removeprefix("backbone.").replace(".default.", ".")
            if key in live_adapter:
                raise ValueError("Ambiguous adapter parameter names")
            live_adapter[key] = parameter
        elif name.startswith("head."):
            live_head[name.removeprefix("head.")] = parameter
    if not live_adapter or set(live_head) != {"weight", "bias"}:
        raise ValueError("Complete live LoRA and scalar-head parameters are required")
    saved_adapter = load_file(str(output / "adapter/adapter_model.safetensors"), device="cpu")
    saved_head = torch.load(output / "head.pt", map_location="cpu", weights_only=True)
    for label, live, saved in (("adapter", live_adapter, saved_adapter), ("head", live_head, saved_head)):
        if not isinstance(saved, dict) or set(saved) != set(live):
            raise ValueError("Checkpoint " + label + " tensor names differ")
        for name, parameter in live.items():
            value = saved[name]
            if (not isinstance(value, torch.Tensor) or value.shape != parameter.shape or value.dtype != parameter.dtype
                    or not torch.isfinite(value).all()):
                raise ValueError("Checkpoint tensor shape/dtype/value differs: " + name)
    with torch.no_grad():
        for live, saved in ((live_adapter, saved_adapter), (live_head, saved_head)):
            for name, parameter in live.items():
                parameter.copy_(saved[name])
    return {"kind": "adapter_head_reload_into_existing_pinned_sharded_base", "model": model.model_id,
            "revision": model.revision, "trainable_tensor_count": len(live_adapter) + len(live_head),
            "frozen_base_reloaded": False}
