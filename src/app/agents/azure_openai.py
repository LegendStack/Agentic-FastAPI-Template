import logging
from typing import Any

import httpx
from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

from ..core.config import settings
from ..core.credentials import AzureOpenAICredentialFactory


def get_azure_openai_chat() -> AzureChatOpenAI:
    """
    Returns a configured Azure OpenAI Chat model.
    DEPRECATED: Use get_llm_service().chat_model instead.
    """
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

    def __init__(self, use_mocks: bool = False):
        self.use_mocks = use_mocks
        self._client = None
        self._sync_client = None

        if use_mocks:
            from .demo.mocks.mock_llm import MockLLM

            self.chat_model = MockLLM()
            self.embeddings_model = MockLLM()
            logger.info("LLMService: Initialized with Mocks")
        else:
            # We share both sync and async clients to satisfy langchain-openai requirements
            # while still preventing session leaks via singleton pattern.
            self._client = httpx.AsyncClient(timeout=60.0)
            self._sync_client = httpx.Client(timeout=60.0)

            # Get authentication provider
            provider = AzureOpenAICredentialFactory.get_provider(settings)

            common_params = {
                "azure_deployment": settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
                "openai_api_version": settings.AZURE_OPENAI_API_VERSION,
                "azure_endpoint": settings.AZURE_OPENAI_ENDPOINT,
                "http_client": self._sync_client,
                "http_async_client": self._client,
            }

            if settings.AZURE_OPENAI_AUTH_MODE == "api_key":
                common_params["api_key"] = settings.AZURE_OPENAI_API_KEY.get_secret_value()
            else:
                # For Managed Identity or OAuth2, we provide a token provider function
                async def get_token() -> str:
                    creds = await provider.get_credentials()
                    return creds.token.access_token

                common_params["azure_ad_token_provider"] = get_token

            self.chat_model = AzureChatOpenAI(
                **common_params,
                temperature=0.3,
            )

            # Embeddings use same endpoint but different deployment
            embedding_params = common_params.copy()
            embedding_params["azure_deployment"] = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME

            self.embeddings_model = AzureOpenAIEmbeddings(
                **embedding_params,
            )
            logger.info(f"LLMService: Initialized with Azure OpenAI (Mode: {settings.AZURE_OPENAI_AUTH_MODE})")

    async def get_embeddings(self, text: str) -> list[float]:
        """Generate embeddings for a given text."""
        if self.use_mocks:
            return await self.embeddings_model.get_embeddings(text)
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
        if self._client:
            await self._client.aclose()
        if self._sync_client:
            self._sync_client.close()


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Returns a singleton instance of LLMService."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(use_mocks=settings.BACKLOG_USE_MOCKS)
    return _llm_service
