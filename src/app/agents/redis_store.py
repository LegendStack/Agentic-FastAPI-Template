import json
import logging
from typing import Any

import numpy as np

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class RedisVectorStore(BaseVectorStore):
    """
    Redis implementation of the Vector Store using RediSearch.
    Supports Vector Similarity Search (HNSW/FLAT) and metadata filtering.
    """

    def __init__(self, redis_url: str, index_name: str = "agent-index", embedding_dimension: int = 1536):
        self.redis_url = redis_url
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension
        self._client = None
        self._index_created = False

    async def _get_client(self):
        """Lazy initialization of the Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError("redis is required for Redis Vector Store. Install with: pip install redis")
        return self._client

    async def create_index_if_not_exists(self):
        """
        Ensure the RediSearch index exists with vector search configuration.
        """
        if self._index_created:
            return

        client = await self._get_client()
        try:
            # Check if index exists
            await client.ft(self.index_name).info()
            self._index_created = True
            logger.info(f"RedisVectorStore: Index '{self.index_name}' already exists.")
        except Exception:
            logger.info(f"RedisVectorStore: Creating index '{self.index_name}'...")

            # Define schema
            try:
                from redis.commands.search.field import TagField, TextField, VectorField
            except ImportError:
                # Fallback for older versions or specific environments
                from redis.commands.search.fields import TagField, TextField, VectorField

            try:
                from redis.commands.search.index_definition import IndexDefinition, IndexType
            except ImportError:
                # Fallback for Windows-style casing in some redis-py versions
                from redis.commands.search.indexDefinition import IndexDefinition, IndexType

            # Define schema
            schema = (
                TextField("content"),
                TagField("tenantId"),
                TagField("sourceId"),
                TextField("metadata"),  # Searchable metadata as JSON string
                VectorField(
                    "contentVector",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.embedding_dimension,
                        "DISTANCE_METRIC": "COSINE",
                        "INITIAL_CAP": 1000,
                    },
                ),
            )

            # Create index
            await client.ft(self.index_name).create_index(
                fields=schema,
                definition=IndexDefinition(prefix=[f"doc:{self.index_name}:"], index_type=IndexType.HASH),
            )
            self._index_created = True
            logger.info(f"RedisVectorStore: Index '{self.index_name}' created successfully.")

    async def add_documents(self, documents: list[dict[str, Any]], ids: list[str] | None = None) -> list[str]:
        """
        Add documents to Redis.
        Expected format: {'content': '...', 'embedding': [...], 'metadata': {...}}
        """
        await self.create_index_if_not_exists()
        client = await self._get_client()

        generated_ids = []
        pipeline = client.pipeline()

        for i, doc in enumerate(documents):
            doc_id = ids[i] if ids else f"doc_{i}_{hash(doc['content'])}"
            generated_ids.append(doc_id)

            redis_key = f"doc:{self.index_name}:{doc_id}"

            # Prepare metadata
            metadata = doc.get("metadata", {})
            metadata_str = json.dumps(metadata)

            mapping = {
                "content": doc["content"],
                "contentVector": np.array(doc["embedding"], dtype=np.float32).tobytes(),
                "tenantId": doc.get("tenant_id", "default"),
                "sourceId": doc.get("source_id", ""),
                "metadata": metadata_str,
            }

            pipeline.hset(redis_key, mapping=mapping)

        await pipeline.execute()
        logger.info(f"RedisVectorStore: Indexed {len(generated_ids)} documents.")
        return generated_ids

    async def similarity_search(
        self,
        query_vector: list[float],
        k: int = 4,
        filters: dict[str, Any] | None = None,
        search_text: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform KNN similarity search with optional filtering.
        """
        await self.create_index_if_not_exists()
        client = await self._get_client()

        # Build query string
        # Initial query matches everything or specific text
        base_query = search_text if search_text else "*"

        # Apply filters via TagFields
        filter_parts = []
        if filters:
            if "tenant_id" in filters:
                filter_parts.append(f"@tenantId:{{{filters['tenant_id']}}}")
            if "source_id" in filters:
                filter_parts.append(f"@sourceId:{{{filters['source_id']}}}")

        if filter_parts:
            base_query = f"({' '.join(filter_parts)}) {base_query}"

        from redis.commands.search.query import Query

        # KNN Query: [base_query]=>[KNN $k @vector_field $query_vector AS score]
        query_str = f"({base_query})=>[KNN {k} @contentVector $vec_param AS score]"

        query = (
            Query(query_str)
            .sort_by("score")
            .paging(0, k)
            .return_fields("id", "content", "metadata", "sourceId", "score")
            .dialect(2)
        )

        query_params = {"vec_param": np.array(query_vector, dtype=np.float32).tobytes()}

        results = await client.ft(self.index_name).search(query, query_params=query_params)

        docs = []
        for res in results.docs:
            # Parse metadata back
            metadata_str = getattr(res, "metadata", "{}")
            try:
                metadata = json.loads(metadata_str)
            except Exception:
                metadata = {"raw": metadata_str}

            # Map score (Redis returns distance, so we might need to normalize or label)
            docs.append(
                {
                    "id": res.id.split(":")[-1],  # Strip prefix
                    "content": res.content,
                    "metadata": metadata,
                    "source_id": getattr(res, "sourceId", None),
                    "score": float(res.score),
                }
            )

        return docs

    async def delete_documents(self, ids: list[str]) -> None:
        """Remove documents from Redis."""
        client = await self._get_client()
        pipeline = client.pipeline()
        for doc_id in ids:
            pipeline.delete(f"doc:{self.index_name}:{doc_id}")
        await pipeline.execute()
        logger.info(f"RedisVectorStore: Deleted {len(ids)} documents.")

    async def close(self):
        """Close the Redis client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
