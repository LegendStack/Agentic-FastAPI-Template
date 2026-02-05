import asyncio
import logging
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from app.core.config import settings
from app.agents.azure_openai import LLMService
from app.agents.vector_stores import VectorStoreFactory

import httpx
from app.agents.backlog.nodes.export_node import ExportNode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_azure_openai():
    logger.info("Testing Azure OpenAI connection...")
    try:
        llm = LLMService()
        # Test chat completion
        response = await llm.chat([{"role": "user", "content": "Hello, respond with 'Ok' if you can hear me."}])
        logger.info(f"Azure OpenAI Chat: {response}")
        
        # Test embeddings
        embedding = await llm.get_embeddings("Hello world")
        logger.info(f"Azure OpenAI Embeddings: Success (dimension: {len(embedding)})")
        return True
    except Exception as e:
        logger.error(f"Azure OpenAI Test Failed: {e}")
        return False

async def test_azure_search():
    logger.info("Testing Azure AI Search connection...")
    try:
        # Note: We need a mock DB session if we go through VectorStoreFactory
        # but AzureAISearchStore doesn't actually use it.
        store = VectorStoreFactory.get_store(None)
        
        # Test basic retrieval (even if empty)
        query_vector = [0.0] * 1536 # Dummy vector
        results = await store.similarity_search(query_vector, k=1)
        logger.info(f"Azure AI Search: Connection successful. Results: {len(results)}")
        return True
    except Exception as e:
        logger.error(f"Azure AI Search Test Failed: {e}")
        return False

async def test_jira():
    logger.info("Testing JIRA connection...")
    try:
        # We'll use the ExportNode's internal validation
        from app.agents.backlog.config import BacklogAgentConfig
        config = BacklogAgentConfig()
        node = ExportNode(config=config)
        
        if not node._validate_jira_config():
            logger.error("JIRA Configuration is incomplete in settings.")
            return False
            
        # Test basic project retrieval
        url = f"{settings.JIRA_URL}/rest/api/3/project"
        auth = httpx.BasicAuth(settings.JIRA_USERNAME, settings.JIRA_API_TOKEN.get_secret_value())
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, auth=auth)
            if resp.status_code == 200:
                projects = resp.json()
                logger.info(f"JIRA: Connection successful. Found {len(projects)} projects.")
                return True
            else:
                logger.error(f"JIRA: Connection failed - {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        logger.error(f"JIRA Test Failed: {e}")
        return False

async def main():
    print("\nStarting Real System Integration Verification...")
    print("-" * 50)
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Azure Search Enabled: {settings.RAG_BACKEND}")
    print(f"Backlog Mocks Enabled: {settings.BACKLOG_USE_MOCKS}")
    
    openai_ok = await test_azure_openai()
    search_ok = await test_azure_search()
    jira_ok = await test_jira()
    
    print("-" * 50)
    if openai_ok and search_ok and jira_ok:
        print("SUCCESS: All real systems (OpenAI, Search, JIRA) are reachable!")
    else:
        print("FAILURE: Some systems are unreachable. Check your .env file.")

if __name__ == "__main__":
    asyncio.run(main())
