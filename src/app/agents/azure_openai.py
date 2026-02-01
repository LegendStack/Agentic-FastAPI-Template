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
        self.chat_model = get_azure_openai_chat()
        self.embeddings_model = get_azure_openai_embeddings()

    async def get_embeddings(self, text: str) -> list[float]:
        """Generate embeddings for a given text."""
        embedding = await self.embeddings_model.aembed_query(text)
        return embedding

    async def get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = await self.embeddings_model.aembed_documents(texts)
        return embeddings
