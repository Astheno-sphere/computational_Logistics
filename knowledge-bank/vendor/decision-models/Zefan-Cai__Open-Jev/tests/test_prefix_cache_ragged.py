"""Opt-in ragged suffix batching (JEV_RAGGED_SUFFIX=1) must score like the uncached path.

The default cached path never pads (see test_prefix_cache). Ragged mode right-pads
each question's suffixes into one batch and reads each row at its last real token;
these checks prove the logits still match independent uncached scoring, that padding
really happened (so the path under test was exercised), and that the processed-token
count reports every slot the model actually ran, padding included.
"""
import copy
import os
import unittest
from unittest.mock import patch

# Import the module, not PrefixCacheTest itself: a TestCase class bound in this
# module's globals would be collected and run a second time from this file.
from tests import test_prefix_cache as base
from tests.test_prefix_cache import HAS_RUNTIME, PROFILES, mixed_request, tiny_model

if HAS_RUNTIME:
    import torch
    from jev.api import compile_request


@unittest.skipUnless(HAS_RUNTIME, "requires torch, transformers and peft")
class RaggedSuffixTest(unittest.TestCase):
    assert_rows_close = base.PrefixCacheTest.assert_rows_close

    def test_ragged_batches_match_uncached_scoring(self):
        request = mixed_request()
        records = compile_request(request["state"], request["questions"])
        original = copy.deepcopy(records)
        for profile in PROFILES:
            for lora in (False, True):
                model = tiny_model(profile, lora=lora)
                with torch.inference_mode():
                    expected = model(records)
                weights = {key: value.clone() for key, value in model.state_dict().items()}
                for batch_size in (1, 2, 4, 8):
                    with self.subTest(profile=profile, lora=lora, batch_size=batch_size):
                        calls = []

                        def observe(module, args, kwargs):
                            mask = kwargs["attention_mask"]
                            calls.append((tuple(kwargs["input_ids"].shape), bool(mask.all())))

                        hook = model.backbone.register_forward_pre_hook(observe, with_kwargs=True)
                        try:
                            with patch.dict(os.environ, {"JEV_RAGGED_SUFFIX": "1"}):
                                actual, stats = model.score_cached(records, batch_size=batch_size)
                        finally:
                            hook.remove()
                        self.assert_rows_close(actual, expected)
                        self.assertEqual(actual[2][0].item(), 0.0)  # Noul false logit.
                        if batch_size > 1:
                            self.assertTrue(any(not full for _, full in calls),
                                            "ragged mode never padded; the path was not exercised")
                        self.assertEqual(stats["processed_input_tokens"],
                                         sum(size * length for (size, length), _ in calls))
                        self.assertLessEqual(max(size for (size, _), _ in calls), batch_size)
                        self.assertEqual(records, original)
                        for name, value in model.state_dict().items():
                            torch.testing.assert_close(value, weights[name], atol=0, rtol=0)

    def test_ragged_mode_uses_fewer_suffix_calls(self):
        request = mixed_request()
        records = compile_request(request["state"], request["questions"])
        model = tiny_model(next(iter(PROFILES)))
        _, bucketed = model.score_cached(records, batch_size=8)
        with patch.dict(os.environ, {"JEV_RAGGED_SUFFIX": "1"}):
            _, ragged = model.score_cached(records, batch_size=8)
        self.assertLessEqual(ragged["suffix_batches"], bucketed["suffix_batches"])


if __name__ == "__main__":
    unittest.main()
