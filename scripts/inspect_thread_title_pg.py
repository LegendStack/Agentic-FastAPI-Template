
import asyncio
import os
import sys

# Add src to sys.path
sys.path.append(os.getcwd())

from src.app.core.db.database import async_get_db
from src.app.agents.conversations import ConversationService

async def check_thread():
    try:
        async with async_get_db() as db:
            service = ConversationService(db)
            thread_id = 'a40ab737-385b-4c77-b83c-0afc726fbd29'
            conv = await service.get_conversation(thread_id)
            if conv:
                print(f"ID: {conv.id}")
                print(f"Thread ID: {conv.thread_id}")
                print(f"Title: {conv.title}")
                print(f"Updated At: {conv.updated_at}")
                
                messages = await service.get_messages(thread_id, limit=5)
                print("\nLast 5 Messages:")
                for m in messages:
                    print(f"[{m.role}]: {m.content[:100]}...")
            else:
                print(f"Thread {thread_id} not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_thread())
