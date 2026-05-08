import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from src.config.settings import settings

from .base_client import BaseLLMClient, normalize_content


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI with normalized content output.

    The Responses API returns content as a list of typed blocks
    (reasoning, text, etc.). ``invoke`` normalizes to string for
    consistent downstream handling. ``with_structured_output`` defaults
    to function-calling so the Responses-API parse path is avoided
    (langchain-openai's parse path emits noisy
    PydanticSerializationUnexpectedValue warnings per call without
    affecting correctness).

    Provider-specific quirks (e.g. DeepSeek's thinking mode) live in
    purpose-built subclasses below so this base class stays small.
    """

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))

    def with_structured_output(self, schema, *, method=None, **kwargs):
        if method is None:
            method = "function_calling"
        return super().with_structured_output(schema, method=method, **kwargs)


class OpenAICompatibleClient(BaseLLMClient):
    """Client for OpenAI-compatible API endpoints.

    Works with: OpenAI, LiteLLM, Ollama, vLLM, xAI, etc.
    Configured via LLM_API_KEY and LLM_BASE_URL environment variables.
    """

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        return NormalizedChatOpenAI(
            model=self.model,
            api_key=settings.llm_api_key,
            base_url=self.base_url,
            **self.kwargs,
        )

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return True
