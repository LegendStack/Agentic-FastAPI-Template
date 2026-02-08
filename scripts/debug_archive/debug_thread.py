import asyncio

from sqlalchemy import select
from src.app.agents.conversations.models import DatabaseMessage

from src.app.agents.persistence import SqlAlchemyCheckpointSaver
from src.app.core.db.database import async_get_db


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
            if state.values.get("stories"):
                print(
                    f"First Story Title: {state.values.get('stories')[0].get('title') if isinstance(state.values.get('stories')[0], dict) else state.values.get('stories')[0].title}"
                )
        break


if __name__ == "__main__":
    thread_id = "304ad185-5b39-486f-85e2-6358ef00c62d"
    asyncio.run(check_thread(thread_id))
