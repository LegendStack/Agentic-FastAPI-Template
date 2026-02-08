import logging
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
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

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Asynchronously retrieve a checkpoint tuple."""
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
            # Use self.serde.loads_typed to deserialize the checkpoint
            # Our column stores it as a wrapped JSON dict with type and data (hex)
            checkpoint_data = row.checkpoint
            if isinstance(checkpoint_data, dict) and "type" in checkpoint_data and "data" in checkpoint_data:
                checkpoint_type = checkpoint_data["type"]
                checkpoint_bytes = bytes.fromhex(checkpoint_data["data"])
                checkpoint = self.serde.loads_typed((checkpoint_type, checkpoint_bytes))
            else:
                # Fallback for older formats if any
                checkpoint = checkpoint_data

            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=row.metadata_json,
                parent_config={"configurable": {"thread_id": thread_id, "checkpoint_id": row.parent_id}}
                if row.parent_id
                else None,
            )
        return None

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Asynchronously store a new checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]

        # Use self.serde.dumps_typed to get a serializable representation
        checkpoint_type, checkpoint_bytes = self.serde.dumps_typed(checkpoint)
        serialized_checkpoint = {"type": checkpoint_type, "data": checkpoint_bytes.hex()}

        stmt = insert(LangGraphCheckpoint).values(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            parent_id=checkpoint.get("parent_id"),
            checkpoint=serialized_checkpoint,
            metadata_json=metadata,
        )
        await self.db.execute(stmt)
        await self.db.commit()

        return config

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Asynchronously list checkpoints."""
        query = select(LangGraphCheckpoint)
        if config:
            query = query.where(LangGraphCheckpoint.thread_id == config["configurable"]["thread_id"])

        query = query.order_by(LangGraphCheckpoint.checkpoint_id.desc())
        if limit:
            query = query.limit(limit)

        result = await self.db.execute(query)
        for row in result.scalars():
            checkpoint_data = row.checkpoint
            if isinstance(checkpoint_data, dict) and "type" in checkpoint_data and "data" in checkpoint_data:
                checkpoint_type = checkpoint_data["type"]
                checkpoint_bytes = bytes.fromhex(checkpoint_data["data"])
                checkpoint = self.serde.loads_typed((checkpoint_type, checkpoint_bytes))
            else:
                checkpoint = checkpoint_data

            yield CheckpointTuple(
                config={"configurable": {"thread_id": row.thread_id, "checkpoint_id": row.checkpoint_id}},
                checkpoint=checkpoint,
                metadata=row.metadata_json,
                parent_config={"configurable": {"thread_id": row.thread_id, "checkpoint_id": row.parent_id}}
                if row.parent_id
                else None,
            )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Asynchronously store intermediate writes (No-op for now)."""
        # For simple graphs, writes can be ignored or handled during aput
        pass

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Synchronously store intermediate writes (No-op for now)."""
        pass

    async def adelete_thread(self, thread_id: str) -> None:
        """Delete conversation history."""
        from sqlalchemy import delete

        stmt = delete(LangGraphCheckpoint).where(LangGraphCheckpoint.thread_id == thread_id)
        await self.db.execute(stmt)
        await self.db.commit()

    def delete_thread(self, thread_id: str) -> None:
        """Delete conversation history."""
        raise NotImplementedError("Use adelete_thread instead")

    # Sync versions are required by some LangGraph components even in async apps
    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        raise NotImplementedError("Use aget_tuple instead")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        raise NotImplementedError("Use aput instead")

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        raise NotImplementedError("Use alist instead")

    # Note: Modern LangGraph uses specialized interfaces, this is a simplified version
    # for the boilerplate blueprint.
