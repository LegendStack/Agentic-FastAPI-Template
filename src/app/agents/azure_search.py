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
        self._index_client = None

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

    async def _get_index_client(self):
        """Lazy initialization of the Azure Search Index client."""
        if self._index_client is None:
            try:
                from azure.core.credentials import AzureKeyCredential
                from azure.search.documents.indexes.aio import SearchIndexClient

                self._index_client = SearchIndexClient(
                    endpoint=self.endpoint, credential=AzureKeyCredential(self.api_key)
                )
            except ImportError:
                raise ImportError(
                    "azure-search-documents is required for Azure AI Search. "
                    "Install with: pip install azure-search-documents"
                )
        return self._index_client

    async def create_index_if_not_exists(self):
        """Create the search index if it doesn't exist."""
        index_client = await self._get_index_client()
        
        try:
            # Check if index exists
            indices = []
            async for index in index_client.list_indexes():
                indices.append(index.name)
            
            if self.index_name in indices:
                logger.info(f"AzureAISearch: Index '{self.index_name}' already exists.")
                return

            logger.info(f"AzureAISearch: Creating index '{self.index_name}'...")
            
            from azure.search.documents.indexes.models import (
                SearchIndex,
                SearchField,
                SearchFieldDataType,
                SimpleField,
                SearchableField,
                VectorSearch,
                HnswAlgorithmConfiguration,
                VectorSearchProfile,
            )

            # Define the fields
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
                SearchField(
                    name="contentVector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=self.embedding_dimension,
                    vector_search_profile_name="my-vector-profile",
                ),
                SimpleField(name="sourceId", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="tenantId", type=SearchFieldDataType.String, filterable=True),
                # Metadata as stringified JSON to keep it simple and flexible
                SearchableField(name="metadata", type=SearchFieldDataType.String, filterable=True),
            ]

            # Vector search configuration
            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="my-algorithms-config",
                    )
                ],
                profiles=[
                    VectorSearchProfile(
                        name="my-vector-profile",
                        algorithm_configuration_name="my-algorithms-config",
                    )
                ],
            )

            index = SearchIndex(
                name=self.index_name,
                fields=fields,
                vector_search=vector_search
            )

            await index_client.create_index(index)
            logger.info(f"AzureAISearch: Index '{self.index_name}' created successfully.")

        except Exception as e:
            logger.error(f"AzureAISearch: Error ensuring index exists - {e}")
            raise

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
        # Ensure index exists first (Phase 13 fix)
        await self.create_index_if_not_exists()
        
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
                "metadata": str(doc.get("metadata", {})), # Store as string for SearchableField
            }
            search_docs.append(search_doc)

        result = await client.upload_documents(documents=search_docs)
        logger.info(f"Uploaded {len(result)} documents to Azure AI Search")

        return generated_ids

    async def similarity_search(
        self, 
        query_vector: list[float], 
        k: int = 4, 
        filters: dict[str, Any] | None = None,
        search_text: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Perform vector similarity search with optional OData filtering.
        Supports hybrid search combining vector + keyword for better results.
        """
        # Ensure index exists first (Phase 13 fix)
        await self.create_index_if_not_exists()
        
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

            results = await client.search(
                search_text=search_text, 
                vector_queries=[vector_query], 
                filter=filter_string, 
                top=k
            )

            docs = []
            async for result in results:
                # Parse metadata back from string if it looks like a dict
                metadata_str = result.get("metadata", "{}")
                try:
                    import ast
                    metadata = ast.literal_eval(metadata_str) if isinstance(metadata_str, str) else metadata_str
                except Exception:
                    metadata = {"raw": metadata_str}

                docs.append(
                    {
                        "id": result["id"],
                        "content": result["content"],
                        "metadata": metadata,
                        "source_id": result.get("sourceId"),
                        "score": result["@search.score"],
                    }
                )

            return docs

        except ImportError:
            raise ImportError("azure-search-documents>=11.4.0 is required for vector search.")

    async def delete_documents(self, ids: list[str]) -> None:
        """Remove documents from the index by ID."""
        # Ensure index exists first (Phase 13 fix)
        await self.create_index_if_not_exists()
        
        client = await self._get_client()
        documents = [{"id": doc_id} for doc_id in ids]
        await client.delete_documents(documents=documents)
        logger.info(f"Deleted {len(ids)} documents from Azure AI Search")

    async def close(self):
        """Close the client connection."""
        if self._client:
            await self._client.close()
            self._client = None
