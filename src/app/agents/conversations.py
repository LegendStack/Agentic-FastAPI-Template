"""
Conversation service for managing chat threads and message history.
"""

import uuid
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.agentic import Conversation, Message


class ConversationService:
    """Service for managing conversations and messages."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(
        self,
        agent_name: str = "doc_assistant",
        user_id: int | None = None,
        tenant_id: str | None = None,
        title: str | None = None,
        thread_id: str | None = None,
    ) -> Conversation:
        """Create a new conversation thread."""
        conversation = Conversation(
            thread_id=thread_id or f"thread_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            tenant_id=tenant_id,
            agent_name=agent_name,
            title=title or "New Conversation",
            status="active",
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def get_conversation(self, thread_id: str) -> Conversation | None:
        """Get a conversation by thread_id."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.thread_id == thread_id).options(selectinload(Conversation.messages))
        )
        return result.scalars().first()

    async def get_conversation_by_id(self, conversation_id: int) -> Conversation | None:
        """Get a conversation by ID."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.messages))
        )
        return result.scalars().first()

    async def list_conversations(
        self,
        user_id: int | None = None,
        tenant_id: str | None = None,
        agent_name: str | None = None,
        status: str = "active",
        limit: int = 20,
        offset: int = 0,
        days_limit: int | None = None,
    ) -> list[Conversation]:
        """List conversations with optional filtering."""
        query = select(Conversation).where(Conversation.status == status)

        if user_id:
            query = query.where(Conversation.user_id == user_id)
        if tenant_id:
            query = query.where(Conversation.tenant_id == tenant_id)
        if agent_name:
            query = query.where(Conversation.agent_name == agent_name)

        if days_limit:
            min_date = datetime.utcnow() - timedelta(days=days_limit)
            query = query.where(
                sa.or_(
                    Conversation.updated_at >= min_date,
                    Conversation.created_at >= min_date
                )
            )

        query = query.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_conversation_title(self, thread_id: str, title: str) -> Conversation | None:
        """Update conversation title."""
        await self.db.execute(
            update(Conversation)
            .where(Conversation.thread_id == thread_id)
            .values(title=title, updated_at=datetime.utcnow())
        )
        await self.db.commit()
        return await self.get_conversation(thread_id)

    async def update_metadata(self, thread_id: str, metadata: dict) -> Conversation | None:
        """Update conversation metadata."""
        conv = await self.get_conversation(thread_id)
        if conv:
             current_metadata = dict(conv.metadata_json or {})
             current_metadata.update(metadata)
             await self.db.execute(
                 update(Conversation)
                 .where(Conversation.thread_id == thread_id)
                 .values(metadata_json=current_metadata, updated_at=datetime.utcnow())
             )
             await self.db.commit()
             return conv
        return None

    async def archive_conversation(self, thread_id: str) -> bool:
        """Archive a conversation (soft delete)."""
        result = await self.db.execute(
            update(Conversation)
            .where(Conversation.thread_id == thread_id)
            .values(status="archived", updated_at=datetime.utcnow())
        )
        await self.db.commit()
        return result.rowcount > 0

    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        tool_calls: dict | None = None,
        attachments: list[dict] | None = None,
    ) -> Message:
        """Add a message to a conversation."""
        # Get or create conversation
        conversation = await self.get_conversation(thread_id)
        if not conversation:
            conversation = await self.create_conversation(thread_id=thread_id)

        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_calls=tool_calls,
            attachments=attachments or [],
        )
        self.db.add(message)

        # Update conversation's updated_at
        conversation.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_messages(self, thread_id: str, limit: int = 50, before_id: int | None = None) -> list[Message]:
        """Get messages for a conversation with pagination."""
        conversation = await self.get_conversation(thread_id)
        if not conversation:
            return []

        query = select(Message).where(Message.conversation_id == conversation.id)

        if before_id:
            query = query.where(Message.id < before_id)

        query = query.order_by(Message.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        messages = list(result.scalars().all())
        messages.reverse()  # Return in chronological order
        return messages
