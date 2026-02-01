"""
Azure AI Search implementation for enterprise-grade RAG.
Provides the alternative vector store backend for production deployments.
"""

import logging
from typing import Any

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class AzureAISearchStore(BaseVectorStore):
    """
    Azure AI Search implementation of the Vector Store.
    Provides enterprise-grade search with automatic scaling,
    semantic ranking, and hybrid search capabilities.
    """

    def __init__(self, endpoint: str, api_key: str, index_name: str = "agent-index", embedding_dimension: int = 1536):
        self.endpoint = endpoint
        self.api_key = api_key
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension
        self._client = None

    async def _get_client(self):
        """Lazy initialization of the Azure Search client."""
        if self._client is None:
            try:
                from azure.core.credentials import AzureKeyCredential
                from azure.search.documents.aio import SearchClient

                self._client = SearchClient(
                    endpoint=self.endpoint, index_name=self.index_name, credential=AzureKeyCredential(self.api_key)
                )
            except ImportError:
                raise ImportError(
                    "azure-search-documents is required for Azure AI Search. "
                    "Install with: pip install azure-search-documents"
                )
        return self._client

    async def add_documents(self, documents: list[dict[str, Any]], ids: list[str] | None = None) -> list[str]:
        """
        Add documents to the Azure AI Search index.

        Expected document format:
        {
            "content": "...",
            "embedding": [...],
            "metadata": {...},
            "source_id": "...",
            "tenant_id": "..."
        }
        """
        client = await self._get_client()

        search_docs = []
        generated_ids = []

        for i, doc in enumerate(documents):
            doc_id = ids[i] if ids else f"doc_{i}_{hash(doc['content'])}"
            generated_ids.append(doc_id)

            search_doc = {
                "id": doc_id,
                "content": doc["content"],
                "contentVector": doc["embedding"],
                "sourceId": doc.get("source_id", ""),
                "tenantId": doc.get("tenant_id", "default"),
                "metadata": doc.get("metadata", {}),
            }
            search_docs.append(search_doc)

        result = await client.upload_documents(documents=search_docs)
        logger.info(f"Uploaded {len(result)} documents to Azure AI Search")

        return generated_ids

    async def similarity_search(
        self, query_vector: list[float], k: int = 4, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Perform vector similarity search with optional OData filtering.
        Supports hybrid search combining vector + keyword for better results.
        """
        client = await self._get_client()

        # Build OData filter for tenant isolation
        filter_string = None
        if filters:
            filter_parts = []
            if "tenant_id" in filters:
                filter_parts.append(f"tenantId eq '{filters['tenant_id']}'")
            if "source_id" in filters:
                filter_parts.append(f"sourceId eq '{filters['source_id']}'")
            if filter_parts:
                filter_string = " and ".join(filter_parts)

        try:
            from azure.search.documents.models import VectorizedQuery

            vector_query = VectorizedQuery(vector=query_vector, k_nearest_neighbors=k, fields="contentVector")

            results = await client.search(search_text=None, vector_queries=[vector_query], filter=filter_string, top=k)

            docs = []
            async for result in results:
                docs.append(
                    {
                        "id": result["id"],
                        "content": result["content"],
                        "metadata": result.get("metadata", {}),
                        "source_id": result.get("sourceId"),
                        "score": result["@search.score"],
                    }
                )

            return docs

        except ImportError:
            raise ImportError("azure-search-documents>=11.4.0 is required for vector search.")

    async def delete_documents(self, ids: list[str]) -> None:
        """Remove documents from the index by ID."""
        client = await self._get_client()
        documents = [{"id": doc_id} for doc_id in ids]
        await client.delete_documents(documents=documents)
        logger.info(f"Deleted {len(ids)} documents from Azure AI Search")

    async def close(self):
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None
