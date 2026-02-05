
import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from app.core.config import settings
from app.agents.conversations import ConversationService

async def debug_db_fetch():
    print("🚀 Debugging DB Fetch...")
    
    # Needs DB URL. Assuming settings loads it.
    print(f"DB URL: {settings.POSTGRES_URL}")
    
    engine = create_async_engine(str(settings.POSTGRES_URL))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        service = ConversationService(db)
        
        # Try to list conversations to get a valid ID
        convs = await service.list_conversations(limit=1)
        if not convs:
            print("No conversations found.")
            return

        thread_id = convs[0].thread_id
        print(f"Testing fetch for thread: {thread_id}")
        
        try:
            messages = await service.get_messages(thread_id, limit=5)
            print(f"Fetched {len(messages)} messages.")
            for m in messages:
                print(f"- {m.role}: {len(m.content)} chars, In: {m.input_tokens}")
        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_db_fetch())
