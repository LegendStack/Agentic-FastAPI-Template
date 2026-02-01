"""
Confluence Indexer.
===================
Index pages from Atlassian Confluence Cloud or Server.

Supports incremental syncing and space-based filtering.
"""

import logging
from datetime import datetime
from typing import Any

from .base import BaseIndexer, BaseVectorStore

logger = logging.getLogger(__name__)


class ConfluenceIndexer(BaseIndexer):
    """
    Indexer for Confluence pages and blog posts.

    Supports:
    - Confluence Cloud
    - Confluence Server/Data Center
    - Space-based filtering
    - Incremental sync via modified dates

    Usage:
        indexer = ConfluenceIndexer(
            vector_store=vector_store,
            llm_service=llm_service,
            base_url="https://company.atlassian.net/wiki",
            username="email@company.com",
            api_token="...",
            spaces=["PRODUCT", "ENGINEERING"]
        )
        result = await indexer.run()
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        llm_service,  # LLMService for embeddings
        base_url: str,
        username: str,
        api_token: str,
        spaces: list[str] | None = None,
        tenant_id: str | None = None,
        include_attachments: bool = False,
        max_pages: int = 1000,
    ):
        self.vector_store = vector_store
        self.llm = llm_service
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.spaces = spaces
        self.tenant_id = tenant_id
        self.include_attachments = include_attachments
        self.max_pages = max_pages
        self._last_sync: datetime | None = None

    async def _get_pages(self, space_key: str | None = None) -> list[dict[str, Any]]:
        """Fetch pages from Confluence API."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx required. Install with: pip install httpx")

        auth = (self.username, self.api_token)

        pages = []
        start = 0
        limit = 50

        async with httpx.AsyncClient(auth=auth) as client:
            while len(pages) < self.max_pages:
                # Build CQL query
                cql = "type=page"
                if space_key:
                    cql += f" AND space={space_key}"
                if self._last_sync:
                    cql += f" AND lastModified >= '{self._last_sync.strftime('%Y-%m-%d')}'"

                url = f"{self.base_url}/rest/api/content/search"
                params = {"cql": cql, "start": start, "limit": limit, "expand": "body.storage,version,space"}

                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    break

                for page in results:
                    pages.append(
                        {
                            "id": page["id"],
                            "title": page["title"],
                            "space_key": page.get("space", {}).get("key", ""),
                            "content": page.get("body", {}).get("storage", {}).get("value", ""),
                            "version": page.get("version", {}).get("number", 1),
                            "url": f"{self.base_url}{page.get('_links', {}).get('webui', '')}",
                        }
                    )

                start += limit

                if len(results) < limit:
                    break

        return pages

    def _html_to_text(self, html: str) -> str:
        """Convert HTML content to plain text."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style"]):
                element.decompose()

            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            # Fallback: basic tag stripping
            import re

            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            return " ".join(text.split())

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        """Chunk text with overlap."""
        if not text.strip():
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end].strip())
            start = end - overlap
        return [c for c in chunks if c]

    async def run(self, force: bool = False) -> dict[str, Any]:
        """
        Run the indexing process.

        Args:
            force: If True, reindex all pages. Otherwise, incremental.
        """
        if force:
            self._last_sync = None

        logger.info(f"Starting Confluence indexing: {self.base_url}")

        all_pages = []

        if self.spaces:
            for space in self.spaces:
                pages = await self._get_pages(space)
                all_pages.extend(pages)
        else:
            all_pages = await self._get_pages()

        indexed = 0
        errors = 0

        for page in all_pages:
            try:
                text = self._html_to_text(page["content"])

                if not text.strip():
                    continue

                chunks = self._chunk_text(text)

                if not chunks:
                    continue

                embeddings = await self.llm.embed(chunks)

                docs = [
                    {
                        "content": chunk,
                        "embedding": emb,
                        "source_id": f"confluence:{page['id']}",
                        "tenant_id": self.tenant_id,
                        "metadata": {
                            "source": "confluence",
                            "page_id": page["id"],
                            "title": page["title"],
                            "space_key": page["space_key"],
                            "url": page["url"],
                            "chunk_index": i,
                        },
                    }
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
                ]

                await self.vector_store.add_documents(docs)
                indexed += len(docs)

            except Exception as e:
                logger.error(f"Error indexing page {page.get('title', 'unknown')}: {e}")
                errors += 1

        self._last_sync = datetime.utcnow()

        return {
            "source": "confluence",
            "base_url": self.base_url,
            "spaces": self.spaces,
            "pages_processed": len(all_pages),
            "chunks_indexed": indexed,
            "errors": errors,
        }
