from typing import Any, Sequence
from llama_index.llms.vllm import VllmServer
from llama_index.core.llms.callbacks import (
    llm_chat_callback,
)
from llama_index.core.base.llms.types import (
    ChatMessage, 
    ChatResponse,
    MessageRole,
)
from openai import OpenAI
from openai import AsyncOpenAI


class OpenAIvLLM(VllmServer):
    use_async: bool = False
    
    def __init__(self, *args, api_key: str = None, use_async: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        print("Initializing OpenAIvLLM with model:", self.model, "and API URL:", self.api_url, "and API Key:", api_key)

        self.use_async = use_async
        if self.use_async:
            self._openai_client = AsyncOpenAI(
                base_url=self.api_url,
                api_key=api_key,
            )
        else:
            self._openai_client = OpenAI(
                base_url=self.api_url,
                api_key=api_key,
            )

    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        assert self.use_async is False, "Synchronous chat method called on an async client. Use achat instead."

        kwargs = kwargs if kwargs else {}
        # prompt = self.messages_to_prompt(messages)
        # completion_response = self.complete(prompt, **kwargs)
        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": c.role,
                "content": c.content,
            } for c in messages],
            **kwargs,
        )
        return ChatResponse(
            message=ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response.choices[0].message.content,
                additional_kwargs={},
            ),
            raw="",
        )
    
    @llm_chat_callback()
    async def achat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        assert self.use_async is True, "Asynchronous chat method called on a synchronous client. Use chat instead."
        
        kwargs = kwargs if kwargs else {}
        # prompt = self.messages_to_prompt(messages)
        # completion_response = self.complete(prompt, **kwargs)
        response = await self._openai_client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": c.role,
                "content": c.content,
            } for c in messages],
            **kwargs,
        )
        return ChatResponse(
            message=ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response.choices[0].message.content,
                additional_kwargs={},
            ),
            raw="",
        )
    

    
    
