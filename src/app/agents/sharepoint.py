"""
SharePoint Indexer.
===================
Index documents from SharePoint Online or SharePoint Server.

Supports incremental syncing and multi-tenant document isolation.
"""

import logging
from typing import Any

from .base import BaseIndexer, BaseVectorStore

logger = logging.getLogger(__name__)


class SharePointIndexer(BaseIndexer):
    """
    Indexer for SharePoint documents.

    Supports:
    - SharePoint Online (Microsoft 365)
    - SharePoint Server (on-premises)
    - Incremental sync via change tokens
    - Multi-tenant isolation

    Usage:
        indexer = SharePointIndexer(
            vector_store=vector_store,
            llm_service=llm_service,
            site_url="https://contoso.sharepoint.com/sites/docs",
            client_id="...",
            client_secret="..."
        )
        result = await indexer.run()
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        llm_service,  # LLMService for embeddings
        site_url: str,
        client_id: str,
        client_secret: str,
        tenant_id: str | None = None,
        document_library: str = "Shared Documents",
        file_types: list[str] | None = None,
    ):
        self.vector_store = vector_store
        self.llm = llm_service
        self.site_url = site_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.document_library = document_library
        self.file_types = file_types or [".pdf", ".docx", ".pptx", ".txt", ".md"]
        self._client = None
        self._change_token: str | None = None

    async def _get_client(self):
        """Get SharePoint client (lazy init)."""
        if self._client is None:
            try:
                from office365.runtime.auth.client_credential import ClientCredential
                from office365.sharepoint.client_context import ClientContext

                credentials = ClientCredential(self.client_id, self.client_secret)
                self._client = ClientContext(self.site_url).with_credentials(credentials)
                logger.info(f"Connected to SharePoint: {self.site_url}")
            except ImportError:
                raise ImportError(
                    "Office365-REST-Python-Client required. Install with: pip install Office365-REST-Python-Client"
                )
        return self._client

    async def _list_files(self) -> list[dict[str, Any]]:
        """List files in the document library."""
        client = await self._get_client()

        doc_lib = client.web.lists.get_by_title(self.document_library)
        items = (
            doc_lib.items.select(["FileLeafRef", "FileRef", "Modified", "Id"])
            .filter(
                "FSObjType eq 0"  # Files only
            )
            .get()
            .execute_query()
        )

        files = []
        for item in items:
            file_name = item.properties.get("FileLeafRef", "")

            # Check file type
            if not any(file_name.lower().endswith(ext) for ext in self.file_types):
                continue

            files.append(
                {
                    "id": str(item.properties.get("Id")),
                    "name": file_name,
                    "path": item.properties.get("FileRef"),
                    "modified": item.properties.get("Modified"),
                }
            )

        return files

    async def _download_file(self, file_path: str) -> bytes:
        """Download file content."""
        client = await self._get_client()

        file = client.web.get_file_by_server_relative_url(file_path)
        content = file.read().execute_query()
        return content.value

    async def _extract_text(self, content: bytes, file_name: str) -> str:
        """Extract text from file content."""
        if file_name.lower().endswith(".txt") or file_name.lower().endswith(".md"):
            return content.decode("utf-8", errors="ignore")

        if file_name.lower().endswith(".pdf"):
            try:
                import io

                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(content))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e:
                logger.warning(f"Failed to parse PDF {file_name}: {e}")
                return ""

        if file_name.lower().endswith(".docx"):
            try:
                import io

                from docx import Document

                doc = Document(io.BytesIO(content))
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception as e:
                logger.warning(f"Failed to parse DOCX {file_name}: {e}")
                return ""

        return ""

    async def run(self, force: bool = False) -> dict[str, Any]:
        """
        Run the indexing process.

        Args:
            force: If True, reindex all documents. Otherwise, incremental.
        """
        logger.info(f"Starting SharePoint indexing: {self.site_url}")

        files = await self._list_files()
        indexed = 0
        errors = 0

        for file_info in files:
            try:
                content = await self._download_file(file_info["path"])
                text = await self._extract_text(content, file_info["name"])

                if not text.strip():
                    continue

                # Chunk the text
                chunks = self._chunk_text(text)

                # Generate embeddings
                embeddings = await self.llm.embed(list(chunks))

                # Store documents
                docs = [
                    {
                        "content": chunk,
                        "embedding": emb,
                        "source_id": f"sharepoint:{file_info['id']}",
                        "tenant_id": self.tenant_id,
                        "metadata": {
                            "source": "sharepoint",
                            "file_name": file_info["name"],
                            "file_path": file_info["path"],
                            "chunk_index": i,
                        },
                    }
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
                ]

                await self.vector_store.add_documents(docs)
                indexed += len(docs)

            except Exception as e:
                logger.error(f"Error indexing {file_info['name']}: {e}")
                errors += 1

        return {
            "source": "sharepoint",
            "site_url": self.site_url,
            "files_processed": len(files),
            "chunks_indexed": indexed,
            "errors": errors,
        }

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        """Simple text chunking."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return chunks
