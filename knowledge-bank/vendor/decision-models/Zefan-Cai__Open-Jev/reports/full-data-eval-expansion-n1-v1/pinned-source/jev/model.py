"""Independent candidate scoring; no autoregressive generation or JSON decoding."""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn
from transformers import AutoModelForImageTextToText, AutoTokenizer

from .api import candidate_prompts


class DecisionModel(nn.Module):
    def __init__(self, model_id, revision, device="cuda:0", lora_rank=8, max_length=384):
        super().__init__()
        self.model_id, self.revision = model_id, revision
        self.max_length, self.device_name = max_length, device
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.tokenizer.padding_side = "right"
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        full = AutoModelForImageTextToText.from_pretrained(
            model_id, revision=revision, torch_dtype=torch.bfloat16,
            attn_implementation="sdpa", device_map={"": device},
        )
        # Initialize a discriminative scalar from the pretrained Yes/No readout.
        yes = self.tokenizer.encode("Yes", add_special_tokens=False)
        no = self.tokenizer.encode("No", add_special_tokens=False)
        if len(yes) != 1 or len(no) != 1:
            raise ValueError("The Yes/No baseline requires single-token labels")
        initial = (full.get_output_embeddings().weight[yes[0]] -
                   full.get_output_embeddings().weight[no[0]]).detach().float().clone()
        self.backbone = full.model.language_model
        hidden_size = self.backbone.config.hidden_size
        del full
        self.backbone.config.use_cache = False
        self.backbone.requires_grad_(False)
        self.head = nn.Linear(hidden_size, 1, bias=True, device=device, dtype=torch.float32)
        with torch.no_grad():
            self.head.weight.copy_(initial.unsqueeze(0))
            self.head.bias.zero_()
        del initial
        if lora_rank:
            from peft import LoraConfig, get_peft_model
            targets = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "out_proj"]
            available = {name.rsplit(".", 1)[-1] for name, _ in self.backbone.named_modules()}
            targets = [name for name in targets if name in available]
            if not targets:
                raise ValueError("No intended LoRA target modules found")
            self.backbone = get_peft_model(self.backbone, LoraConfig(
                r=lora_rank, lora_alpha=lora_rank * 2, target_modules=targets,
                lora_dropout=0.0, bias="none",
            ))
            self.backbone.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
            self.backbone.enable_input_require_grads()
        self.lora_rank = lora_rank

    def forward(self, records):
        prompts, counts = [], []
        for record in records:
            entries = candidate_prompts(record)
            counts.append(len(entries))
            for prompt in entries:
                prompts.append(self.tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}], tokenize=False,
                    add_generation_prompt=True, enable_thinking=False,
                ))
        encoded = self.tokenizer(prompts, padding=True, truncation=False, return_tensors="pt")
        lengths = encoded["attention_mask"].sum(-1)
        self.last_input_tokens = int(lengths.sum().item())
        if lengths.max().item() > self.max_length:
            raise ValueError(f"Input length {lengths.max().item()} exceeds max_length={self.max_length}; no silent truncation")
        encoded = {k: v.to(self.device_name) for k, v in encoded.items()}
        outputs = self.backbone(**encoded, use_cache=False, return_dict=True)
        idx = torch.arange(len(prompts), device=self.device_name)
        hidden = outputs.last_hidden_state[idx, lengths.to(self.device_name) - 1]
        scores = self.head(hidden.float()).squeeze(-1)
        logits, offset = [], 0
        for record, count in zip(records, counts):
            values = scores[offset:offset + count]
            if record["kind"] == "noul":
                values = torch.stack([torch.zeros_like(values[0]), values[0]])
            logits.append(values)
            offset += count
        return logits

    def save(self, output):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        if self.lora_rank:
            self.backbone.save_pretrained(output / "adapter")
        torch.save(self.head.state_dict(), output / "head.pt")
        (output / "model.json").write_text(json.dumps({
            "model_id": self.model_id, "revision": self.revision,
            "max_length": self.max_length, "lora_rank": self.lora_rank,
            "method": "independent_candidate_lora_nll_brier",
        }, indent=2) + "\n")

    @classmethod
    def load(cls, output, device="cuda:0"):
        output = Path(output)
        config = json.loads((output / "model.json").read_text())
        model = cls(config["model_id"], config["revision"], device=device,
                    lora_rank=0, max_length=config["max_length"])
        if config["lora_rank"]:
            from peft import PeftModel
            model.backbone = PeftModel.from_pretrained(model.backbone, output / "adapter")
            model.lora_rank = config["lora_rank"]
        model.head.load_state_dict(torch.load(output / "head.pt", map_location=device, weights_only=True))
        return model.eval()
