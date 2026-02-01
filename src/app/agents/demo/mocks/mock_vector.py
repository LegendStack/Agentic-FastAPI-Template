"""
Mock Vector Store
==================
An in-memory vector store for testing and demo purposes.
Pre-populated with sample documents about LegendStack.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MockDocument:
    """A document with content and metadata."""
    id: str
    content: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MockVectorStore:
    """
    An in-memory vector store for demo and testing.
    
    Features:
    - Pre-populated with sample LegendStack documentation
    - Cosine similarity search
    - Supports add/delete/search operations
    
    Usage:
        store = MockVectorStore()
        results = await store.similarity_search(query_vector, k=3)
    """
    
    # Pre-populated sample documents
    SAMPLE_DOCS = [
        {
            "id": "doc_1",
            "content": "LegendStack is an enterprise-ready Agentic AI framework. It provides production-ready components for building intelligent agents with FastAPI and LangGraph.",
            "metadata": {"source": "readme", "topic": "overview"},
        },
        {
            "id": "doc_2", 
            "content": "The RAG pipeline uses pgvector for efficient similarity search. Documents are chunked, embedded, and stored with metadata for filtering.",
            "metadata": {"source": "docs", "topic": "rag"},
        },
        {
            "id": "doc_3",
            "content": "Graph-RAG extends traditional RAG by incorporating Neo4j relationships. This enables discovery of related entities and contextual expansion.",
            "metadata": {"source": "docs", "topic": "graph-rag"},
        },
        {
            "id": "doc_4",
            "content": "Entity-Aware Memory extracts people, projects, and systems from conversations. These entities are stored in Neo4j for cross-thread recall.",
            "metadata": {"source": "docs", "topic": "memory"},
        },
        {
            "id": "doc_5",
            "content": "Zero-Trust Security ensures data isolation with tenant-specific encryption. Each tenant's data is encrypted with a derived key.",
            "metadata": {"source": "docs", "topic": "security"},
        },
        {
            "id": "doc_6",
            "content": "Semantic Caching stores LLM responses based on query similarity. This reduces latency and costs for repeated questions.",
            "metadata": {"source": "docs", "topic": "caching"},
        },
        {
            "id": "doc_7",
            "content": "The Reflector pattern enables self-correction. If response quality is low, the agent critiques and regenerates its answer.",
            "metadata": {"source": "docs", "topic": "reflector"},
        },
        {
            "id": "doc_8",
            "content": "Safety Guardrails include PII masking and content moderation. Sensitive data is automatically detected and masked before processing.",
            "metadata": {"source": "docs", "topic": "safety"},
        },
    ]
    
    def __init__(self):
        """Initialize with sample documents."""
        self.documents: list[MockDocument] = []
        self._load_sample_docs()
        
    def _load_sample_docs(self):
        """Load pre-defined sample documents with mock embeddings."""
        for doc_data in self.SAMPLE_DOCS:
            # Generate deterministic embedding from content
            embedding = self._generate_embedding(doc_data["content"])
            doc = MockDocument(
                id=doc_data["id"],
                content=doc_data["content"],
                embedding=embedding,
                metadata=doc_data["metadata"],
            )
            self.documents.append(doc)
        logger.info(f"MockVectorStore: Loaded {len(self.documents)} sample documents")
    
    def _generate_embedding(self, text: str) -> list[float]:
        """Generate a deterministic mock embedding from text."""
        import random
        hash_val = hash(text.lower())
        random.seed(hash_val)
        embedding = [random.uniform(-1, 1) for _ in range(1536)]
        random.seed()
        return embedding
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
    
    async def similarity_search(
        self, 
        query_vector: list[float], 
        k: int = 4,
        filter_metadata: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query_vector: The query embedding
            k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of matching documents with scores
        """
        results = []
        
        for doc in self.documents:
            # Apply metadata filter if provided
            if filter_metadata:
                match = all(
                    doc.metadata.get(key) == value 
                    for key, value in filter_metadata.items()
                )
                if not match:
                    continue
            
            score = self._cosine_similarity(query_vector, doc.embedding)
            results.append({
                "id": doc.id,
                "content": doc.content,
                "metadata": doc.metadata,
                "score": score,
            })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(f"MockVectorStore: Found {len(results[:k])} results")
        return results[:k]
    
    async def add_documents(self, documents: list[dict[str, Any]]) -> list[str]:
        """Add documents to the store."""
        ids = []
        for doc_data in documents:
            doc = MockDocument(
                id=doc_data.get("id", f"doc_{len(self.documents) + 1}"),
                content=doc_data["content"],
                embedding=doc_data.get("embedding", self._generate_embedding(doc_data["content"])),
                metadata=doc_data.get("metadata", {}),
            )
            self.documents.append(doc)
            ids.append(doc.id)
        return ids
    
    async def delete_documents(self, ids: list[str]) -> None:
        """Delete documents by ID."""
        self.documents = [doc for doc in self.documents if doc.id not in ids]
