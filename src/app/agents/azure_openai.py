from typing import Any

import httpx
from langchain_core.messages import BaseMessage
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

from ..core.config import settings


def get_azure_openai_chat() -> AzureChatOpenAI:
    """Returns a configured Azure OpenAI Chat model."""
    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
        raise ValueError("Azure OpenAI credentials not configured.")

    return AzureChatOpenAI(
        azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
        openai_api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY.get_secret_value(),
        temperature=0,
    )


def get_azure_openai_embeddings() -> AzureOpenAIEmbeddings:
    """Returns a configured Azure OpenAI Embeddings model."""
    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
        raise ValueError("Azure OpenAI credentials not configured.")

    return AzureOpenAIEmbeddings(
        azure_deployment=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME,
        openai_api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY.get_secret_value(),
    )


class LLMService:
    """Wrapper for LLM operations to ensure consistency across the boilerplate."""

    def __init__(self):
        # We share both sync and async clients to satisfy langchain-openai requirements
        # while still preventing session leaks via singleton pattern.
        self._client = httpx.AsyncClient(timeout=60.0)
        self._sync_client = httpx.Client(timeout=60.0)

        self.chat_model = AzureChatOpenAI(
            azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
            openai_api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY.get_secret_value(),
            temperature=0,
            http_client=self._sync_client,
            http_async_client=self._client,
        )
        self.embeddings_model = AzureOpenAIEmbeddings(
            azure_deployment=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME,
            openai_api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY.get_secret_value(),
            http_client=self._sync_client,
            http_async_client=self._client,
        )

    async def get_embeddings(self, text: str) -> list[float]:
        """Generate embeddings for a given text."""
        embedding = await self.embeddings_model.aembed_query(text)
        return embedding

    async def get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = await self.embeddings_model.aembed_documents(texts)
        return embeddings

    async def chat(self, messages: list[dict[str, str]] | list[BaseMessage]) -> Any:
        """Send a message list to the chat model."""
        return await self.chat_model.ainvoke(messages)

    async def close(self):
        """Close the internal HTTP clients."""
        await self._client.aclose()
        self._sync_client.close()


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Returns a singleton instance of LLMService."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
