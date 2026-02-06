import os
import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...agents.azure_openai import LLMService
from ...agents.background import enqueue_agent_task, get_task_status
from ...agents.hitl import hitl_manager
from ...agents.indexers import DocumentIndexer
from ...agents.persistence import SqlAlchemyCheckpointSaver
from ...agents.sample_agent import DocAssistantAgent
from ...agents.streaming import StreamingChatResponse, sse_stream
from ...agents.vector_stores import VectorStoreFactory
from ...core.db.database import async_get_db

router = APIRouter(tags=["agents"])


# ============================================
# Document Indexing
# ============================================


@router.post("/agents/index-file")
async def index_file(file: UploadFile = File(...), db: Annotated[AsyncSession, Depends(async_get_db)] = None):
    """Endpoint to upload and index a product document."""
    temp_dir = "/tmp/agent_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        llm_service = LLMService()
        vector_store = VectorStoreFactory.get_store(db)
        indexer = DocumentIndexer(vector_store, llm_service)
        result = await indexer.run(file_path=file_path)
        return result
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


# ============================================
# Chat Endpoints
# ============================================


@router.post("/agents/chat")
async def agent_chat(
    message: str, thread_id: str = "default-thread", db: Annotated[AsyncSession, Depends(async_get_db)] = None
):
    """Endpoint to chat with the Doc Assistant agent (persisted)."""
    checkpointer = SqlAlchemyCheckpointSaver(db)
    agent = DocAssistantAgent(db, checkpointer=checkpointer)
    response = await agent.chat(message, thread_id)
    return response


@router.post("/agents/chat/stream")
async def agent_chat_stream(
    request: Request,
    message: str,
    thread_id: str = "default-thread",
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
):
    """SSE streaming chat endpoint for real-time token responses."""
    checkpointer = SqlAlchemyCheckpointSaver(db)
    agent = DocAssistantAgent(db, checkpointer=checkpointer)

    async def token_generator():
        # In a real implementation, this would yield tokens from the LLM
        response = await agent.chat(message, thread_id)
        for char in response.get("content", ""):
            yield char

    streaming_response = StreamingChatResponse()
    return await sse_stream(streaming_response.stream_tokens(token_generator()), request)


# ============================================
# Background Tasks
# ============================================


@router.post("/agents/tasks/enqueue")
async def enqueue_task(agent_name: str = "doc_assistant", message: str = "", thread_id: str | None = None):
    """Enqueue a background agent task for async execution."""
    task_id = await enqueue_agent_task(
        task_name="run_agent_task", agent_name=agent_name, input_data={"message": message}, thread_id=thread_id
    )
    return {"task_id": task_id, "status": "queued"}


@router.get("/agents/tasks/{task_id}")
async def get_task(task_id: str):
    """Get the status of a background agent task."""
    result = await get_task_status(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


# ============================================
# Human-in-the-Loop (HITL)
# ============================================


class HITLApprovalRequest(BaseModel):
    reviewer: str
    notes: str | None = None


class HITLRejectRequest(BaseModel):
    reviewer: str
    reason: str


@router.get("/agents/hitl/pending")
async def get_pending_hitl_requests(thread_id: str | None = None, agent_name: str | None = None):
    """Get all pending HITL requests."""
    requests = await hitl_manager.get_pending_requests(thread_id, agent_name)
    return {"requests": [r.model_dump() for r in requests]}


@router.get("/agents/hitl/{request_id}")
async def get_hitl_request(request_id: str):
    """Get a specific HITL request status."""
    request = await hitl_manager.get_request_status(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="HITL request not found")
    return request.model_dump()


@router.post("/agents/hitl/{request_id}/approve")
async def approve_hitl_request(request_id: str, approval: HITLApprovalRequest):
    """Approve a pending HITL request."""
    try:
        request = await hitl_manager.approve(request_id, approval.reviewer, approval.notes)
        return request.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/agents/hitl/{request_id}/reject")
async def reject_hitl_request(request_id: str, rejection: HITLRejectRequest):
    """Reject a pending HITL request."""
    try:
        request = await hitl_manager.reject(request_id, rejection.reviewer, rejection.reason)
        return request.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================
# Conversations & Messages
# ============================================

from ...agents.conversations import ConversationService


class CreateConversationRequest(BaseModel):
    agent_name: str = "doc_assistant"
    title: str | None = None
    tenant_id: str | None = None


class UpdateConversationRequest(BaseModel):
    title: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    input_tokens: int
    output_tokens: int
    created_at: str

    class Config:
        from_attributes = True


@router.post("/agents/conversations")
async def create_conversation(
    request: CreateConversationRequest, db: Annotated[AsyncSession, Depends(async_get_db)] = None
):
    """Create a new conversation thread."""
    service = ConversationService(db)
    conversation = await service.create_conversation(
        agent_name=request.agent_name, title=request.title, tenant_id=request.tenant_id
    )
    return {
        "id": conversation.id,
        "thread_id": conversation.thread_id,
        "title": conversation.title,
        "agent_name": conversation.agent_name,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
    }


@router.get("/agents/conversations")
async def list_conversations(
    agent_name: str | None = None,
    tenant_id: str | None = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
):
    """List conversations with optional filtering."""
    service = ConversationService(db)
    # Default to 30 days limit as requested
    conversations = await service.list_conversations(
        agent_name=agent_name,
        tenant_id=tenant_id,
        status=status,
        limit=limit,
        offset=offset,
        days_limit=30,
    )
    return {
        "conversations": [
            {
                "id": c.id,
                "thread_id": c.thread_id,
                "title": c.title,
                "agent_name": c.agent_name,
                "status": c.status,
                "metadata": c.metadata_json,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in conversations
        ]
    }


@router.get("/agents/conversations/{thread_id}")
async def get_conversation(thread_id: str, db: Annotated[AsyncSession, Depends(async_get_db)] = None):
    """Get a conversation with its messages."""
    service = ConversationService(db)
    conversation = await service.get_conversation(thread_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "id": conversation.id,
        "thread_id": conversation.thread_id,
        "title": conversation.title,
        "agent_name": conversation.agent_name,
        "status": conversation.status,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in conversation.messages
        ],
    }


@router.get("/agents/conversations/{thread_id}/messages")
async def get_messages(
    thread_id: str,
    limit: int = 50,
    before_id: int | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
):
    """Get messages for a conversation with pagination."""
    service = ConversationService(db)
    messages = await service.get_messages(thread_id, limit=limit, before_id=before_id)
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "tool_calls": m.tool_calls,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    }


@router.patch("/agents/conversations/{thread_id}")
async def update_conversation(
    thread_id: str, request: UpdateConversationRequest, db: Annotated[AsyncSession, Depends(async_get_db)] = None
):
    """Update conversation title."""
    service = ConversationService(db)
    conversation = await service.update_conversation_title(thread_id, request.title)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "updated", "title": conversation.title}


@router.delete("/agents/conversations/{thread_id}")
async def archive_conversation(thread_id: str, db: Annotated[AsyncSession, Depends(async_get_db)] = None):
    """Archive a conversation (soft delete)."""
    service = ConversationService(db)
    success = await service.archive_conversation(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "archived"}
