import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from llm2jev.backend.sglang.scoring import prepare_score_batches
from test_sglang_fakes import native_modules


class ScoreBatchTests(unittest.TestCase):
    def setUp(self):
        modules = native_modules()
        self.convert = Mock(wraps=modules[
            "sglang.srt.parser.jinja_template_utils"
        ].process_content_for_template_format)
        modules["sglang.srt.parser.jinja_template_utils"].process_content_for_template_format = self.convert
        patcher = patch.dict("sys.modules", modules)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tokenizer = Mock()
        self.tokenizer.return_value = {"input_ids": [[1, 2], [1, 3]]}
        self.processor = SimpleNamespace(image_processor=object(), apply_chat_template=Mock())
        self.processor.apply_chat_template.side_effect = lambda messages, **kwargs: "".join(
            message["content"] if isinstance(message["content"], str) else "".join(
                part["text"] if part["type"] == "text" else "<image>"
                for part in message["content"]
            ) for message in messages
        )
        self.prompts = (
            ({"role": "user", "content": [
                {"type": "text", "text": "first"},
                {"type": "image_url", "image_url": {"url": "red.png"}},
                {"type": "text", "text": "second"},
                {"type": "image_url", "image_url": {"url": "file:///blue.png"}},
            ]},),
            ({"role": "user", "content": "plain text"},),
            ({"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "https://example.test/green.png"}},
            ]},),
        )

    def prepare(self, prompts, submission="all", processor=True):
        return prepare_score_batches(
            self.tokenizer, self.processor if processor else None, prompts,
            enable_thinking=False, submission=submission, no_token_id=9, yes_token_id=7,
        )

    def test_native_conversion_preserves_interleaving_and_mixed_candidate_alignment(self):
        original = copy.deepcopy(self.prompts)
        expected_images = [[str(Path("red.png").resolve()), "file:///blue.png"], [],
                           ["https://example.test/green.png"]]
        for submission in ("all", "staged"):
            batches = self.prepare(self.prompts, submission)
            self.assertEqual([indices for indices, _ in batches],
                             [[0, 1, 2]] if submission == "all" else [[0], [1], [2]])
            self.assertEqual([text for _, args in batches for text in args["text"]],
                             ["first<image>second<image>", "plain text", "<image>"])
            self.assertEqual([[image.url for image in row] for _, args in batches
                              for row in args["image_data"]], expected_images)
            for _, args in batches:
                self.assertIsNone(args["input_ids"])
                self.assertEqual(args["sampling_params"], {"max_new_tokens": 0})
        self.assertEqual(self.convert.call_count, 6)
        self.assertEqual(self.prompts, original)
        self.tokenizer.assert_not_called()

    def test_text_uses_original_tokenizer_even_on_a_vision_model(self):
        prompts = (self.prompts[1], self.prompts[1])
        self.tokenizer.apply_chat_template.return_value = "plain template"
        batches = self.prepare(prompts, submission="staged")
        self.assertEqual([args["input_ids"] for _, args in batches], [[[1, 2]], [[1, 3]]])
        self.tokenizer.apply_chat_template.assert_called_with(
            list(prompts[0]), tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
        self.tokenizer.assert_called_once_with(["plain template"] * 2, add_special_tokens=False)
        self.processor.apply_chat_template.assert_not_called()
        for _, args in batches:
            self.assertIsNone(args["image_data"])
            self.assertIsNone(args["text"])

    def test_text_model_rejects_images_before_rendering_or_submission(self):
        with self.assertRaisesRegex(ValueError, "multimodal SGLang model"):
            self.prepare(self.prompts, processor=False)
        self.tokenizer.apply_chat_template.assert_not_called()
