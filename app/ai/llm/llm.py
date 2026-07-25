from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.config import get_settings


@lru_cache
def get_llm() -> BaseChatModel:
    """
    Returns the configured chat model according
    to the selected provider.
    """

    settings = get_settings()

    provider = settings.llm_provider.lower()

    if provider == "openai":
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
        )

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
