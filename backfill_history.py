import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from src.app.agents.conversations import ConversationService
from src.app.core.db.database import async_get_db
from src.app.models.agentic import LangGraphCheckpoint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill():
    async for db in async_get_db():
        logger.info("Starting backfill...")

        # 1. Get all distinct thread_ids from checkpoints
        # Using a raw query or distinct selection
        stmt = select(LangGraphCheckpoint.thread_id).distinct()
        result = await db.execute(stmt)
        thread_ids = result.scalars().all()

        logger.info(f"Found {len(thread_ids)} threads in checkpoints.")

        service = ConversationService(db)
        count = 0

        for thread_id in thread_ids:
            # Check if exists in conversations
            existing = await service.get_conversation(thread_id)
            if existing:
                continue

            # Need to find a good title.
            # We can try to fetch the latest state for the thread to get "epic_input"
            # Or just default to "Restored Conversation"

            # Let's try to get the latest checkpoint for this thread
            stmt_latest = (
                select(LangGraphCheckpoint)
                .where(LangGraphCheckpoint.thread_id == thread_id)
                .order_by(LangGraphCheckpoint.checkpoint_id.desc())
                .limit(1)
            )

            res = await db.execute(stmt_latest)
            latest_cp = res.scalars().first()

            title = "Restored Conversation"
            timestamp = datetime.utcnow()

            if latest_cp and latest_cp.checkpoint:
                # Try to extract data if possible.
                # Note: The checkpoint data structure is binary/complex.
                # Use a heuristic or default.
                pass

            logger.info(f"Restoring thread {thread_id}...")

            # Create conversation entry
            await service.create_conversation(
                thread_id=thread_id,
                agent_name="backlog_assistant",
                title=title,
                # Use a simple active status
            )
            count += 1

        logger.info(f"Backfilled {count} conversations.")
        return


if __name__ == "__main__":
    asyncio.run(backfill())
