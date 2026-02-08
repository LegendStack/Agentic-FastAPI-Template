import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path("src").resolve()))

from sqlalchemy import select

from app.core.db.database import local_session
from app.models.agentic import Conversation


async def check_db():
    async with local_session() as session:
        result = await session.execute(select(Conversation))
        conversations = result.scalars().all()
        print(f"Checking {len(conversations)} conversations...")

        for c in conversations:
            try:
                if c.created_at is None:
                    print(f"CRITICAL: Conversation {c.id} (thread {c.thread_id}) has NULL created_at")
                else:
                    c.created_at.isoformat()

                if c.updated_at is not None:
                    c.updated_at.isoformat()

            except Exception as e:
                print(f"ERROR on conversation {c.id} (thread {c.thread_id}): {e}")


if __name__ == "__main__":
    asyncio.run(check_db())
