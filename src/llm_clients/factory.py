from typing import Optional

from .base_client import BaseLLMClient


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.

    Provider modules are imported lazily so that simply importing this
    factory (e.g. during test collection) does not pull in heavy LLM SDKs
    or fail when their API keys are absent.

    Args:
        provider: LLM provider name
        model: Model name/identifier
        base_url: Optional base URL for API endpoint
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured BaseLLMClient instance

    Raises:
        ValueError: If provider is not supported
    """

    if provider.lower() == "openai":
        from .openai_client import OpenAICompatibleClient

        return OpenAICompatibleClient(model, base_url, provider="openai", **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
