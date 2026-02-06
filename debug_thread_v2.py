
import asyncio
import json
import os
from sqlalchemy import select
from src.app.core.db.database import async_get_db
from src.app.agents.conversations.models import DatabaseMessage
from src.app.agents.persistence import SqlAlchemyCheckpointSaver

async def check_thread(thread_id):
    async for db in async_get_db():
        # Check messages
        result = await db.execute(
            select(DatabaseMessage)
            .where(DatabaseMessage.conversation_id == thread_id)
            .order_by(DatabaseMessage.created_at)
        )
        messages = result.scalars().all()
        print(f"--- Messages for {thread_id} ---")
        for m in messages:
            print(f"[{m.role}]: {m.content[:200]}...")
        
        # Check checkpoint state
        saver = SqlAlchemyCheckpointSaver(db)
        config = {"configurable": {"thread_id": thread_id}}
        state = await saver.aget_state(config)
        if state and state.values:
            print(f"\n--- State Values for {thread_id} ---")
            print(f"Epic Input: {state.values.get('epic_input')}")
            print(f"Story Count: {len(state.values.get('stories', []))}")
            if state.values.get('stories'):
                try:
                    first_story = state.values.get('stories')[0]
                    title = first_story.get('title') if isinstance(first_story, dict) else first_story.title
                    print(f"First Story Title: {title}")
                except Exception as e:
                    print(f"Error reading stories: {e}")
        break

if __name__ == '__main__':
    import sys
    thread_id = sys.argv[1] if len(sys.argv) > 1 else 'a3a66d92-bf9f-41dd-9be5-38afc1e5c5c8'
    asyncio.run(check_thread(thread_id))
