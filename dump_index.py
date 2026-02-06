
import asyncio
from src.app.core.config import settings
from src.app.agents.vector_stores import VectorStoreFactory

async def dump_index():
    store = VectorStoreFactory.get_store(None)
    client = await store._get_client()
    
    print("--- Index Dump ---")
    results = await client.search(search_text="*", top=100)
    async for r in results:
        print(f"ID: {r.get('id')} | Title: {r.get('metadata')} | Content: {r.get('content')[:100]}...")

if __name__ == '__main__':
    asyncio.run(dump_index())
