
import asyncio
from src.app.core.db.database import async_get_db
from src.app.agents.conversations import ConversationService

async def check_thread():
    async with async_get_db() as db:
        service = ConversationService(db)
        thread_id = 'a40ab737-385b-4c77-b83c-0afc726fbd29'
        conv = await service.get_conversation(thread_id)
        if conv:
            print(f"ID: {conv.id}")
            print(f"Thread ID: {conv.thread_id}")
            print(f"Title: {conv.title}")
            
            messages = await service.get_messages(thread_id)
            print("\nMessages:")
            for m in messages:
                print(f"[{m.role}]: {m.content[:100]}...")
        else:
            print(f"Thread {thread_id} not found")

if __name__ == "__main__":
    asyncio.run(check_thread())
