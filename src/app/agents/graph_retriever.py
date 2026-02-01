"""
Hybrid Graph-RAG Retriever.
==========================
Combines vector-based retrieval with graph-based relationship traversal.
"""

import logging
from typing import Any, Dict, List

from ..core.graph_db import GraphDBClient
from .vector_stores import BaseVectorStore

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

    async def retrieve(self, query_vector: list[float], k: int = 4, depth: int = 1) -> List[Dict[str, Any]]:
        """
        Performs hybrid retrieval.
        """
        # 1. Similarity Search
        vector_results = await self.vector_store.similarity_search(query_vector, k=k)

        # 2. Graph Traversal
        source_ids = [res.get("source_id") for res in vector_results if res.get("source_id")]

        graph_context = []
        if source_ids:
            # Query for related concepts in Neo4j
            cypher = """
            MATCH (n)-[r]-(m)
            WHERE n.id IN $source_ids
            RETURN n.name as source, type(r) as relationship, m.name as target
            LIMIT 10
            """
            graph_results = await self.graph_client.execute_query(cypher, {"source_ids": source_ids})
            graph_context = [f"{res['source']} --{res['relationship']}--> {res['target']}" for res in graph_results]

        # 3. Merge Results
        final_results = []
        for res in vector_results:
            final_results.append({"content": res["content"], "metadata": res.get("metadata", {}), "type": "vector"})

        if graph_context:
            final_results.append(
                {
                    "content": "Graph Relationships:\n" + "\n".join(graph_context),
                    "metadata": {"type": "graph_triplets"},
                    "type": "graph",
                }
            )

        return final_results
