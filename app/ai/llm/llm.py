from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.application.services.prototype_policy import PrototypePolicy
from app.core.config import get_settings


class PrototypeProviderGuard(BaseCallbackHandler):
    """Reject explicit restricted markers before the provider sends a prompt."""

    raise_error = True
    run_inline = True

    def on_chat_model_start(self, serialized, messages, **kwargs):
        PrototypePolicy.mode()
        for batch in messages:
            for message in batch:
                # System messages contain the application's prohibition itself.
                # State and retrieved context are screened at shared entry points.
                if message.type != "system":
                    PrototypePolicy.screen(message.content)


def get_llm() -> BaseChatModel:
    PrototypePolicy.mode()
    return _configured_llm()


@lru_cache
def _configured_llm() -> BaseChatModel:
    """
    Returns the configured chat model according
    to the selected provider.
    """

    settings = get_settings()

    provider = settings.llm_provider.lower()

    if provider == "openai":
        return ChatOpenAI(
            callbacks=[PrototypeProviderGuard()],
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
        )

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            callbacks=[PrototypeProviderGuard()],
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            retries=0,
            thinking_level=settings.gemini_thinking_level,
            temperature=None,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
