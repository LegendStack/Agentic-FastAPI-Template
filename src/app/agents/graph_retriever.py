"""
Hybrid Graph-RAG Retriever.
==========================
Combines vector-based retrieval with graph-based relationship traversal.
"""

import logging
from typing import Any, Dict, List

from .vector_stores import BaseVectorStore
from ..core import config
from ..core.graph_db import GraphDBClient

logger = logging.getLogger(__name__)


class GraphRetriever:
    """
    Retriever that leverages both vector search and a knowledge graph.

    Workflow:
    1. Perform similarity search on vector store.
    2. Extract entities/IDs from vector results.
    3. Query Neo4j for related nodes/triplets.
    4. Merge and rerank results.
    """

    def __init__(self, vector_store: BaseVectorStore, graph_client: GraphDBClient):
        self.vector_store = vector_store
        self.graph_client = graph_client

    async def retrieve(
        self, query_text: str | None = None, query_vector: list[float] | None = None, k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid retrieval using vector search AND cross-thread entity memory.
        """
        final_results = []
        source_ids = []

        # 1. Similarity Search (Vector)
        if query_vector:
            vector_results = await self.vector_store.similarity_search(query_vector, k=k)
            for res in vector_results:
                final_results.append({"content": res["content"], "metadata": res.get("metadata", {}), "type": "vector"})
                if res.get("source_id"):
                    source_ids.append(res["source_id"])

        # 2. Entity-Aware Memory Retrieval (Graph)
        if getattr(config.settings, "ENABLE_ENTITY_MEMORY", False) and query_text:
            graph_context = await self._fetch_entity_context(query_text, source_ids)
            if graph_context:
                final_results.append(
                    {
                        "content": "Relevant Memory & Relationships:\n" + "\n".join(graph_context),
                        "metadata": {"type": "cross_thread_memory"},
                        "type": "graph",
                    }
                )

        return final_results

    async def _fetch_entity_context(self, query_text: str, vector_source_ids: List[str]) -> List[str]:
        """
        Fetches relationships for entities mentioned in the query AND results.
        """
        # Note: In a production system, we'd use an LLM or NER model here.
        # For the boilerplate, we search for labels matching words in the query.
        cypher = """
        MATCH (n)-[r]-(m)
        WHERE (n.name IN $query_words OR n.id IN $source_ids)
        RETURN n.name as source, type(r) as relationship, m.name as target
        LIMIT 15
        """
        query_words = [w.strip(",.?!").lower() for w in query_text.split() if len(w) > 3]

        try:
            results = await self.graph_client.execute_query(
                cypher, {"query_words": query_words, "source_ids": vector_source_ids}
            )
            return [f"{res['source']} --{res['relationship']}--> {res['target']}" for res in results]
        except Exception as e:
            logger.warning(f"Graph memory retrieval failed: {e}")
            return []
