from datetime import datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base


class DocumentSection(Base):
    """Standard table for storing vectorized document chunks."""

    __tablename__ = "document_section"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True, init=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    metadata_json: Mapped[dict] = mapped_column(sa.JSON, default_factory=dict)
    source_id: Mapped[str | None] = mapped_column(sa.String, index=True, default=None)
    tenant_id: Mapped[str | None] = mapped_column(sa.String, index=True, default=None)


class LangGraphCheckpoint(Base):
    """Table for storing LangGraph state persistence."""

    __tablename__ = "langgraph_checkpoints"

    thread_id: Mapped[str] = mapped_column(sa.String, primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(sa.String, primary_key=True)
    checkpoint: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(sa.String, nullable=True, default=None)


class Conversation(Base):
    """Represents a conversation thread between a user and an agent."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True, init=False)
    thread_id: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    agent_name: Mapped[str] = mapped_column(sa.String(64), default="doc_assistant")
    status: Mapped[str] = mapped_column(sa.String(32), default="active")
    user_id: Mapped[int | None] = mapped_column(sa.ForeignKey("user.id"), index=True, nullable=True, default=None)
    tenant_id: Mapped[str | None] = mapped_column(sa.String(64), index=True, default=None)
    title: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, default_factory=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime, default_factory=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_json: Mapped[dict] = mapped_column(sa.JSON, default_factory=dict)

    # Relationship to messages
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", order_by="Message.created_at", init=False
    )


class Message(Base):
    """Represents a single message in a conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True, init=False)
    conversation_id: Mapped[int] = mapped_column(sa.ForeignKey("conversations.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)

    input_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)

    tool_calls: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True, default=None)
    tool_call_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)

    attachments: Mapped[list] = mapped_column(sa.JSON, default_factory=list)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime, default_factory=datetime.utcnow, index=True)
    metadata_json: Mapped[dict] = mapped_column(sa.JSON, default_factory=dict)

    # Relationship back to conversation
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages", init=False)
