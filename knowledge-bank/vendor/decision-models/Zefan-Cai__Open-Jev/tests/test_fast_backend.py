"""Ownership-transfer and numerical guards for opt-in acceleration."""
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import weakref

from jev.fast_backend import (PROFILE_FIELDS, PROFILES, UPSTREAM_COMMIT,
                              packed_tree_rows, release_copied_layer, validate_profile)

try:
    import torch
    from torch import nn
    from jev.kernels.final_score import final_rms_head, reference_final_rms_head
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
HAS_CUDA_TRITON = HAS_TORCH and torch.cuda.is_available() and importlib.util.find_spec("triton") is not None


def config_for(model_id):
    fields = dict(zip(PROFILE_FIELDS, PROFILES[model_id]))
    return SimpleNamespace(**fields, model_type="qwen3_5_text", head_dim=256,
                           linear_key_head_dim=128, linear_value_head_dim=128,
                           layer_types=["full_attention" if i % 4 == 3 else "linear_attention"
                                        for i in range(fields["num_hidden_layers"])])


class ProfileTest(unittest.TestCase):
    def test_all_three_profiles_are_explicit_for_tail(self):
        for model_id in PROFILES:
            self.assertTrue(validate_profile(model_id, config_for(model_id), "triton-tail")["experimental"])

    def test_unvalidated_smaller_tree_profiles_fail_explicitly(self):
        for model_id in list(PROFILES)[:2]:
            with self.assertRaisesRegex(ValueError, "restricted to the 27B"):
                validate_profile(model_id, config_for(model_id), "fast-cuda")

    def test_config_and_layer_layout_mismatches_fail(self):
        model_id = "Qwen/Qwen3.8-27B"
        cfg = config_for(model_id)
        cfg.hidden_size += 8
        with self.assertRaisesRegex(ValueError, "configuration differs"):
            validate_profile(model_id, cfg, "fast-cuda")
        cfg = config_for(model_id)
        cfg.layer_types[0] = "full_attention"
        with self.assertRaisesRegex(ValueError, "attention layout"):
            validate_profile(model_id, cfg, "fast-cuda")

    def test_unrecognized_model_and_backend_do_not_fallback(self):
        with self.assertRaises(ValueError):
            validate_profile("Qwen/unknown", config_for("Qwen/Qwen3.5-2B"), "triton-tail")
        with self.assertRaises(ValueError):
            validate_profile("Qwen/Qwen3.5-2B", config_for("Qwen/Qwen3.5-2B"), "automatic")

    def test_packed_rows_shares_root_and_question_prefixes(self):
        sequences = [[1, 2, 3, 10], [1, 2, 3, 11], [1, 2, 4, 12], [1, 2, 4, 13]]
        self.assertEqual(packed_tree_rows(sequences, [0, 0, 1, 1]), 32)
        # Long root must not be counted once per candidate.
        prefix = list(range(1024))
        self.assertEqual(packed_tree_rows([prefix + [1], prefix + [2]], [0, 0]), 1056)
        with self.assertRaises(ValueError):
            packed_tree_rows(sequences, [0, 0, 2, 2])

    def test_license_and_pinned_source_are_retained(self):
        root = Path(__file__).resolve().parents[1] / "third_party/open_jev_fast"
        self.assertIn("Copyright (c) 2026 Yiqi Lyu", (root / "LICENSE").read_text())
        self.assertTrue((root / "THIRD_PARTY_NOTICES.md").is_file())
        provenance = json.loads((root / "PROVENANCE.json").read_text())
        self.assertEqual(provenance["commit"], UPSTREAM_COMMIT)
        self.assertEqual(hashlib.sha256((root / "src/kernels.cu").read_bytes()).hexdigest(),
                         provenance["upstream_files"]["src/kernels.cu"]["sha256"])


@unittest.skipUnless(HAS_TORCH, "requires torch")
class OwnershipAndReferenceTest(unittest.TestCase):
    def test_copied_source_projections_are_released_and_output_alias_survives(self):
        for kind, names in (("linear_attention", ("in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a")),
                            ("full_attention", ("q_proj", "k_proj", "v_proj"))):
            layer = nn.Module()
            layer.mlp = nn.Module()
            layer.mlp.gate_proj, layer.mlp.up_proj, layer.mlp.down_proj = [nn.Linear(8, 8, bias=False) for _ in range(3)]
            attention = nn.Module()
            for name in names:
                setattr(attention, name, nn.Linear(8, 8, bias=False))
            attention.out_proj = nn.Linear(8, 8, bias=False)
            setattr(layer, "linear_attn" if kind == "linear_attention" else "self_attn", attention)
            gate_ref = weakref.ref(layer.mlp.gate_proj.weight)
            attention_ref = weakref.ref(getattr(attention, names[0]).weight)
            down_alias = layer.mlp.down_proj.weight
            with torch.no_grad():
                merged = torch.cat((layer.mlp.gate_proj.weight, layer.mlp.up_proj.weight))
            before = merged.clone()
            release_copied_layer(layer, kind)
            gc.collect()
            self.assertIsNone(gate_ref())
            self.assertIsNone(attention_ref())
            self.assertIs(layer.mlp.down_proj.weight, down_alias)
            torch.testing.assert_close(merged, before, atol=0, rtol=0)

    def test_reference_matches_full_dense_qwen_norm_then_head(self):
        generator = torch.Generator().manual_seed(10)
        for dtype in (torch.float32, torch.bfloat16):
            hidden = torch.randn(11, 33, generator=generator).to(dtype)
            delta = torch.randn_like(hidden)
            rows = torch.tensor([0, 4, 10])
            norm = torch.randn(33, generator=generator)
            head = torch.randn(1, 33, generator=generator)
            bias = torch.randn(1, generator=generator)
            x = (hidden + delta).float()
            normalized = (x * torch.rsqrt(x.square().mean(-1, keepdim=True) + 1e-6) * (1 + norm)).to(dtype)
            dense = torch.nn.functional.linear(normalized.float(), head, bias)[rows, 0]
            actual = reference_final_rms_head(hidden, rows, norm, head, bias, delta=delta)
            torch.testing.assert_close(actual, dense, atol=1e-5, rtol=1e-5)

    def test_reference_zero_rows_and_multiplier_convention(self):
        hidden = torch.zeros(4, 16, dtype=torch.bfloat16)
        rows, norm, head, bias = torch.tensor([0, 3]), torch.zeros(16), torch.ones(1, 16), torch.tensor([.125])
        torch.testing.assert_close(reference_final_rms_head(hidden, rows, norm, head, bias), torch.full((2,), .125))
        torch.testing.assert_close(reference_final_rms_head(hidden + 1, rows, norm, head, bias),
                                   reference_final_rms_head(hidden + 1, rows, norm + 1, head, bias, multiplier=True))

    def test_invalid_indices_and_residual_shape_fail(self):
        hidden = torch.ones(4, 16)
        norm, head, bias = torch.zeros(16), torch.ones(1, 16), torch.zeros(1)
        with self.assertRaisesRegex(ValueError, "index outside"):
            reference_final_rms_head(hidden, torch.tensor([4]), norm, head, bias)
        with self.assertRaisesRegex(ValueError, "residual delta"):
            reference_final_rms_head(hidden, torch.tensor([0]), norm, head, bias, delta=torch.ones(3, 16))
        with self.assertRaisesRegex(RuntimeError, "sm80"):
            final_rms_head(hidden, torch.tensor([0]), norm, head, bias)


@unittest.skipUnless(HAS_CUDA_TRITON, "requires CUDA and Triton")
class CudaTailTest(unittest.TestCase):
    def test_all_profile_widths_and_residual_are_close(self):
        for width in (2048, 4096, 5120):
            torch.manual_seed(42)
            hidden = torch.randn(23, width, device="cuda", dtype=torch.bfloat16)
            delta = torch.randn_like(hidden) * .25
            rows = torch.tensor([0, 7, 22], device="cuda")
            norm, head, bias = torch.randn(width, device="cuda") * .01, torch.randn(1, width, device="cuda") * .003, torch.zeros(1, device="cuda")
            for residual in (None, delta):
                actual = final_rms_head(hidden, rows, norm, head, bias, delta=residual)
                expected = reference_final_rms_head(hidden, rows, norm, head, bias, delta=residual)
                torch.testing.assert_close(actual, expected, atol=2e-4, rtol=2e-4)

    def test_out_of_range_cuda_indices_cannot_read_memory(self):
        hidden = torch.ones(4, 2048, device="cuda", dtype=torch.bfloat16)
        result = final_rms_head(hidden, torch.tensor([-1, 4], device="cuda"),
                                torch.zeros(2048, device="cuda"), torch.ones(1, 2048, device="cuda"),
                                torch.zeros(1, device="cuda"))
        self.assertTrue(torch.isnan(result).all().item())
