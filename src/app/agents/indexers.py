import logging
import uuid
from typing import Any

from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredFileLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..core.config import settings
from .azure_openai import LLMService
from .base import BaseIndexer, BaseVectorStore

logger = logging.getLogger(__name__)


class DocumentIndexer(BaseIndexer):
    """Indexer for local files (PDF, TXT, MD)."""

    def __init__(self, vector_store: BaseVectorStore, llm_service: LLMService):
        self.vector_store = vector_store
        self.llm_service = llm_service
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

    async def run(
        self, file_path: str, source_id: str | None = None, tenant_id: str | None = None, force: bool = False
    ) -> dict[str, Any]:
        """Loads, splits, embeds, and indexes a single file."""
        logger.info(f"Indexing file: {file_path}")

        # 1. Load document
        if getattr(settings, "PREFER_UNSTRUCTURED", True):
            loader = UnstructuredFileLoader(file_path)
        elif file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith(".txt") or file_path.endswith(".md"):
            loader = TextLoader(file_path)
        else:
            # Fallback to unstructured
            loader = UnstructuredFileLoader(file_path)

        docs = loader.load()

        # 2. Split document
        chunks = self.text_splitter.split_documents(docs)

        # 3. Embed and Index
        source_id = source_id or f"doc_{uuid.uuid4().hex}"
        documents_to_index = []

        for chunk in chunks:
            embedding = await self.llm_service.get_embeddings(chunk.page_content)
            documents_to_index.append(
                {
                    "content": chunk.page_content,
                    "embedding": embedding,
                    "metadata": chunk.metadata,
                    "source_id": source_id,
                    "tenant_id": tenant_id,
                }
            )

        ids = await self.vector_store.add_documents(documents_to_index)

        return {"source_id": source_id, "chunks_indexed": len(ids), "status": "success"}
