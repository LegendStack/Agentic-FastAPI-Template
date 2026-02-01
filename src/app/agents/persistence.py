import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agentic import LangGraphCheckpoint

logger = logging.getLogger(__name__)


class SqlAlchemyCheckpointSaver(BaseCheckpointSaver):
    """
    LangGraph Checkpoint interface implementation using SQLAlchemy.
    Ensures agent conversations persist across application restarts.
    """

    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db = db_session

    async def aget_tuple(self, config: dict[str, Any]) -> Any | None:
        """Retrieve a checkpoint by thread_id and checkpoint_id."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")

        query = select(LangGraphCheckpoint).where(LangGraphCheckpoint.thread_id == thread_id)
        if checkpoint_id:
            query = query.where(LangGraphCheckpoint.checkpoint_id == checkpoint_id)
        else:
            query = query.order_by(LangGraphCheckpoint.checkpoint_id.desc())

        result = await self.db.execute(query)
        row = result.scalars().first()

        if row:
            return (row.checkpoint, row.metadata_json, row.parent_id)
        return None

    async def aput(self, config: dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata) -> None:
        """Store a new checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]

        stmt = insert(LangGraphCheckpoint).values(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            parent_id=checkpoint.get("parent_id"),
            checkpoint=checkpoint,
            metadata_json=metadata,
        )
        # Handle Upsert if needed, but usually LangGraph uses unique checkpoint IDs
        await self.db.execute(stmt)
        await self.db.commit()

    # Note: Modern LangGraph uses specialized interfaces, this is a simplified version
    # for the boilerplate blueprint.
