"""
RAG Reranking Module.
=====================
Cross-encoder and API-based reranking for improved retrieval quality.

Reranking dramatically improves RAG precision by scoring query-document
relevance more accurately than embedding similarity alone.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseReranker(ABC):
    """Abstract base for reranking implementations."""

    @abstractmethod
    async def rerank(self, query: str, documents: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        """
        Rerank documents by relevance to query.

        Args:
            query: The search query
            documents: List of documents with 'content' and optional metadata
            top_k: Number of top results to return

        Returns:
            Reranked documents with added 'rerank_score' field
        """
        pass


class CrossEncoderReranker(BaseReranker):
    """
    Reranker using sentence-transformers cross-encoder models.

    Cross-encoders score query-document pairs directly, providing
    more accurate relevance scores than bi-encoder embeddings.

    Usage:
        reranker = CrossEncoderReranker()
        results = await reranker.rerank("What is RAG?", documents, top_k=3)
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name)
                logger.info(f"Loaded cross-encoder model: {self.model_name}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers required for CrossEncoderReranker. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    async def rerank(self, query: str, documents: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        """Rerank using cross-encoder scoring."""
        if not documents:
            return []

        model = self._load_model()

        # Create query-document pairs
        pairs = [(query, doc.get("content", "")) for doc in documents]

        # Score all pairs
        scores = model.predict(pairs)

        # Add scores to documents
        scored_docs = []
        for doc, score in zip(documents, scores):
            doc_copy = doc.copy()
            doc_copy["rerank_score"] = float(score)
            scored_docs.append(doc_copy)

        # Sort by score and return top_k
        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored_docs[:top_k]


class CohereReranker(BaseReranker):
    """
    Reranker using Cohere Rerank API.

    Excellent quality, requires Cohere API key.

    Usage:
        reranker = CohereReranker(api_key="...")
        results = await reranker.rerank("What is RAG?", documents)
    """

    def __init__(self, api_key: str, model: str = "rerank-english-v2.0"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import cohere

                self._client = cohere.Client(self.api_key)
            except ImportError:
                raise ImportError("cohere required for CohereReranker. Install with: pip install cohere")
        return self._client

    async def rerank(self, query: str, documents: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        """Rerank using Cohere API."""
        if not documents:
            return []

        client = self._get_client()

        # Extract content for reranking
        doc_texts = [doc.get("content", "") for doc in documents]

        # Call Cohere rerank
        response = client.rerank(model=self.model, query=query, documents=doc_texts, top_n=top_k)

        # Build result with scores
        result = []
        for r in response.results:
            doc_copy = documents[r.index].copy()
            doc_copy["rerank_score"] = r.relevance_score
            result.append(doc_copy)

        return result


class AzureAIReranker(BaseReranker):
    """
    Reranker using Azure AI (placeholder for Azure-native reranking).

    Azure AI Search has built-in semantic ranking which can be used
    as a reranking pass on top of vector search.
    """

    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key

    async def rerank(self, query: str, documents: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        """Rerank using Azure semantic search scoring."""
        # Azure AI Search semantic ranking is typically done at query time
        # This is a placeholder for custom implementation
        logger.warning("AzureAIReranker is a placeholder - use semantic ranking in Azure AI Search")
        return documents[:top_k]


class RerankingService:
    """
    High-level reranking service with pluggable backends.

    Usage:
        service = RerankingService()

        # Add reranker to RAG pipeline
        docs = await vector_store.similarity_search(query_vec, k=20)
        reranked = await service.rerank(query, docs, top_k=5)
    """

    def __init__(self, reranker: BaseReranker | None = None):
        self._reranker = reranker

    def set_reranker(self, reranker: BaseReranker) -> None:
        """Set the reranking implementation."""
        self._reranker = reranker

    async def rerank(self, query: str, documents: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        """Rerank documents. Falls back to original order if no reranker set."""
        if self._reranker is None:
            logger.debug("No reranker configured, returning documents as-is")
            return documents[:top_k]

        return await self._reranker.rerank(query, documents, top_k)
