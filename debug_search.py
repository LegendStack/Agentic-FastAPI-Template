
import asyncio
from src.app.core.config import settings
from src.app.agents.vector_stores import VectorStoreFactory
from src.app.agents.azure_openai import LLMService

async def search_index(query):
    service = LLMService()
    store = VectorStoreFactory.get_store(None)
    
    vector = await service.get_embeddings(query)
    print(f"--- Searching for: '{query}' ---")
    
    results = await store.similarity_search(vector, k=5)
    for r in results:
        print(f"ID: {r.get('id')} | Score: {r.get('score')} | Title: {r.get('metadata', {}).get('title')} | Content: {r.get('content')[:100]}...")

if __name__ == '__main__':
    query = "AI Marketing & Content: Tools that automate content generation, hashtag research, and competitor analysis."
    asyncio.run(search_index(query))
