"""
Tests for Zero-Trust Security (BYOK).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.agents.indexers import DocumentIndexer
from src.app.agents.vector_stores import PgVectorStore
from src.app.core.security_utils import TenantEncryption

@pytest.mark.asyncio
async def test_tenant_encryption_isolation():
    tenant_a = "tenant_alpha"
    tenant_b = "tenant_beta"
    secret_text = "Highly confidential project info"

    # Encrypt for A
    encrypted_a = TenantEncryption.encrypt(secret_text, tenant_a)
    
    # Decrypt for A (Success)
    assert TenantEncryption.decrypt(encrypted_a, tenant_a) == secret_text
    
    # Decrypt for B (Failure)
    decrypted_b = TenantEncryption.decrypt(encrypted_a, tenant_b)
    assert decrypted_b != secret_text

@pytest.mark.asyncio
async def test_indexer_zero_trust_flow():
    mock_db = MagicMock() # Session.add_all is synchronous
    mock_vector = PgVectorStore(mock_db)
    # Patch commit to avoid async errors if called
    mock_db.commit = AsyncMock()
    
    mock_llm = AsyncMock()
    mock_llm.get_embeddings = AsyncMock(return_value=[0.1]*1536)

    indexer = DocumentIndexer(mock_vector, mock_llm)
    
    # Mock Document object
    class MockDoc:
        def __init__(self, content):
            self.page_content = content
            self.metadata = {}

    # Mock file loaders
    with patch("src.app.agents.indexers.TextLoader") as mock_text_loader, \
         patch("src.app.agents.indexers.UnstructuredFileLoader") as mock_unstructured_loader:
        
        mock_docs = [MockDoc("Secret content")]
        mock_text_loader.return_value.load.return_value = mock_docs
        mock_unstructured_loader.return_value.load.return_value = mock_docs
        
        # Run indexing for tenant_a
        await indexer.run("fake.txt", tenant_id="tenant_a")
        
        # Verify that add_all was called with ENCRYPTED content
        mock_db.add_all.assert_called_once()
        args, _ = mock_db.add_all.call_args
        stored_sections = args[0]
        assert stored_sections[0].content != "Secret content"
        assert stored_sections[0].metadata_json["encrypted"] is True
        assert stored_sections[0].tenant_id == "tenant_a"

@pytest.mark.asyncio
async def test_vector_store_decryption():
    mock_db = AsyncMock()
    store = PgVectorStore(mock_db)
    
    # Mock a returned database record (already encrypted)
    tenant_id = "tenant_a"
    raw_text = "Visible content"
    encrypted_text = TenantEncryption.encrypt(raw_text, tenant_id)
    
    # Mocking the SQLAlchemy result
    mock_section = MagicMock()
    mock_section.content = encrypted_text
    mock_section.tenant_id = tenant_id
    mock_section.metadata_json = {"encrypted": True}
    mock_section.id = 1
    mock_section.source_id = "s1"

    mock_scalar_result = MagicMock()
    mock_scalar_result.all.return_value = [mock_section]
    
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalar_result
    
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Search
    results = await store.similarity_search(query_vector=[0.1]*1536)
    
    # Verify decryption
    assert results[0]["content"] == raw_text
