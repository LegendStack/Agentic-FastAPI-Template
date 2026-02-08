import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def inspect_thread(thread_id: str):
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_boilerplate")
    engine = create_async_engine(db_url)

    async with engine.connect() as conn:
        # Check LangGraph checkpoints directly in DB
        result = await conn.execute(
            text("SELECT checkpoint FROM checkpoints WHERE thread_id = :tid ORDER BY checkpoint_id DESC LIMIT 1"),
            {"tid": thread_id},
        )
        row = result.fetchone()

        if not row:
            print(f"No checkpoint found in DB for thread {thread_id}")
            return

        # Checkpoints are often pickled/serialized but sometimes JSON in newer versions
        # Let's try to see if we can get the values from the state
        print(f"--- Thread: {thread_id} ---")
        # Since we can't easily unpickle here without all classes, let's try a different approach
        # Let's use the actual SqlAlchemyCheckpointSaver but with local path

        from src.app.agents.persistence import SqlAlchemyCheckpointSaver

        saver = SqlAlchemyCheckpointSaver(conn)
        state = await saver.aget({"configurable": {"thread_id": thread_id}})

        if not state:
            print("No state retrieved via saver.")
            return

        values = state.get("values", {})
        print(f"Epic Input: {values.get('epic_input')}")
        parsed_epic = values.get("parsed_epic")
        if parsed_epic:
            if isinstance(parsed_epic, dict):
                print(f"Parsed Epic Title: {parsed_epic.get('title')}")
            else:
                print(f"Parsed Epic Title: {getattr(parsed_epic, 'title', 'N/A')}")

        stories = values.get("stories", [])
        print(f"Story Count: {len(stories)}")
        for i, s in enumerate(stories[:10]):
            title = s.get("title") if isinstance(s, dict) else getattr(s, "title", "N/A")
            print(f"  - Story {i + 1}: {title}")

        messages = values.get("messages", [])
        print(f"Message Count: {len(messages)}")
        for m in messages:
            print(f"[{m.get('role')}] {m.get('content')[:100]}...")


if __name__ == "__main__":
    import sys

    tid = sys.argv[1] if len(sys.argv) > 1 else "9db61163-c97a-41f4-9545-e15408aad1fd"
    asyncio.run(inspect_thread(tid))

if __name__ == "__main__":
    import sys

    tid = sys.argv[1] if len(sys.argv) > 1 else "9db61163-c97a-41f4-9545-e15408aad1fd"
    asyncio.run(inspect_thread(tid))
