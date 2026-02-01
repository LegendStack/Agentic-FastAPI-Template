"""
RAG Node - Vector Retrieval
============================
Retrieves relevant documents from the vector store based on query similarity.

This demonstrates the RAG (Retrieval-Augmented Generation) feature.
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState
from ..mocks import MockVectorStore, MockLLM

logger = logging.getLogger(__name__)


class RAGNode:
    """
    RAG retrieval node.
    
    Features:
    - Vector similarity search
    - Configurable k (number of results)
    - Metadata filtering
    
    Usage:
        node = RAGNode(config, vector_store, llm)
        new_state = await node(state)
    """
    
    def __init__(
        self, 
        config: DemoAgentConfig, 
        vector_store: MockVectorStore | Any,
        llm: MockLLM | Any,
    ):
        """Initialize with dependencies."""
        self.config = config
        self.vector_store = vector_store
        self.llm = llm
    
    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Retrieve relevant documents for the query.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with retrieved context
        """
        if not self.config.ENABLE_RAG:
            logger.info("RAGNode: RAG disabled, skipping")
            return {"context": ""}
        
        # Skip if cache hit
        if state.get("cache_hit", False):
            logger.info("RAGNode: Skipping due to cache hit")
            return {}
        
        query = state.get("sanitized_input", state.get("original_input", ""))
        logger.info(f"RAGNode: Retrieving documents for query")
        
        try:
            # Generate query embedding
            query_vector = await self.llm.get_embeddings(query)
            
            # Search vector store
            results = await self.vector_store.similarity_search(
                query_vector=query_vector,
                k=4,
            )
            
            # Format context
            context_parts = []
            for i, doc in enumerate(results, 1):
                context_parts.append(f"[{i}] {doc['content']}")
                logger.debug(f"RAGNode: Retrieved doc {doc['id']} (score: {doc.get('score', 'N/A'):.3f})")
            
            context = "\n\n".join(context_parts)
            logger.info(f"RAGNode: Retrieved {len(results)} documents")
            
            return {"context": context}
            
        except Exception as e:
            logger.error(f"RAGNode: Retrieval failed - {e}")
            return {"context": ""}
