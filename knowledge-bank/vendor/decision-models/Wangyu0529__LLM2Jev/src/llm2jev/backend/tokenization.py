from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..inference.prompt import ChatPrompt


def _single_token_id(tokenizer: Any, label: str, field: str) -> int:
    token_ids = tokenizer.encode(label, add_special_tokens=False)
    if len(token_ids) != 1:
        raise ValueError(f"{field} must encode to exactly one token, got {token_ids}")
    return token_ids[0]


def _apply_chat_template(
    tokenizer: Any,
    prompt: ChatPrompt,
    *,
    enable_thinking: bool,
) -> str:
    return tokenizer.apply_chat_template(
        list(prompt),
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
    )
