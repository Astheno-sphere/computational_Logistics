"""Native API doubles shared by SGLang tests, included in the source distribution."""

import math
from types import SimpleNamespace


class GenerateReqInput(SimpleNamespace):
    def contains_mm_input(self):
        return any(getattr(self, "image_data", None) or [])


def process_content_for_template_format(message, content_format, images, videos, audio, modalities):
    assert content_format == "openai"
    if isinstance(message["content"], str):
        return dict(message)
    parts = []
    for part in message["content"]:
        if part["type"] == "image_url":
            images.append(SimpleNamespace(url=part["image_url"]["url"]))
            parts.append({"type": "image"})
        else:
            parts.append(dict(part))
    return {**message, "content": parts}


def native_modules():
    return {
        "sglang.srt.managers.io_struct": SimpleNamespace(GenerateReqInput=GenerateReqInput),
        "sglang.srt.parser.jinja_template_utils": SimpleNamespace(
            process_content_for_template_format=process_content_for_template_format,
        ),
    }


def score_result(yes=0.8, tokens=100):
    return {"meta_info": {
        "prompt_tokens": tokens, "completion_tokens": 0,
        "output_token_ids_logprobs": [[[math.log(yes), 7, None], [math.log(1 - yes), 9, None]]],
    }}
