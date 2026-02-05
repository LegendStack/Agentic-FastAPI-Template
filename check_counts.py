import asyncio
from src.app.core.db.database import async_get_db
from sqlalchemy import text

async def run():
    async for db in async_get_db():
        r1 = await db.execute(text('SELECT count(*) FROM conversations'))
        r2 = await db.execute(text('SELECT count(*) FROM langgraph_checkpoints'))
        print(f"Conversations: {r1.scalar()}")
        print(f"Checkpoints: {r2.scalar()}")
        return

if __name__ == "__main__":
    asyncio.run(run())
