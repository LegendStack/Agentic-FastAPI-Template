"""
Admin API for Agent Operations.
================================
Endpoints for monitoring and managing agent infrastructure.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...agents.conversations import ConversationService
from ...agents.cost_tracking import LLMCostRecord
from ...agents.hitl import hitl_manager
from ...agents.rate_limiting import rate_limiter
from ...core.db.database import async_get_db
from ...models.agentic import Conversation, Message

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


# ============================================
# Response Models
# ============================================


class AgentStatsResponse(BaseModel):
    total_conversations: int
    active_conversations: int
    total_messages: int
    avg_messages_per_conversation: float
    conversations_last_24h: int
    conversations_last_7d: int


class CostSummaryResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_tokens: int
    total_cost_usd: float
    by_model: dict
    by_tenant: dict


class TenantUsageResponse(BaseModel):
    tenant_id: str
    tokens_used: int
    requests_made: int
    tokens_limit: int
    requests_limit: int
    utilization_percent: float


# ============================================
# Stats Endpoints
# ============================================


@router.get("/stats", response_model=AgentStatsResponse)
async def get_agent_stats(db: Annotated[AsyncSession, Depends(async_get_db)]):
    """Get overall agent statistics."""
    now = datetime.utcnow()

    # Total conversations
    total_result = await db.execute(select(func.count(Conversation.id)))
    total_conversations = total_result.scalar() or 0

    # Active conversations
    active_result = await db.execute(select(func.count(Conversation.id)).where(Conversation.status == "active"))
    active_conversations = active_result.scalar() or 0

    # Total messages
    messages_result = await db.execute(select(func.count(Message.id)))
    total_messages = messages_result.scalar() or 0

    # Average messages per conversation
    avg_messages = total_messages / total_conversations if total_conversations > 0 else 0

    # Last 24h
    day_ago = now - timedelta(days=1)
    day_result = await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= day_ago))
    conversations_24h = day_result.scalar() or 0

    # Last 7 days
    week_ago = now - timedelta(days=7)
    week_result = await db.execute(select(func.count(Conversation.id)).where(Conversation.created_at >= week_ago))
    conversations_7d = week_result.scalar() or 0

    return AgentStatsResponse(
        total_conversations=total_conversations,
        active_conversations=active_conversations,
        total_messages=total_messages,
        avg_messages_per_conversation=round(avg_messages, 2),
        conversations_last_24h=conversations_24h,
        conversations_last_7d=conversations_7d,
    )


@router.get("/conversations")
async def list_admin_conversations(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    tenant_id: str | None = None,
    status: str = "active",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List conversations with admin filters."""
    service = ConversationService(db)
    conversations = await service.list_conversations(tenant_id=tenant_id, status=status, limit=limit, offset=offset)

    return {
        "total": len(conversations),
        "conversations": [
            {
                "id": c.id,
                "thread_id": c.thread_id,
                "user_id": c.user_id,
                "tenant_id": c.tenant_id,
                "agent_name": c.agent_name,
                "title": c.title,
                "status": c.status,
                "message_count": len(c.messages) if hasattr(c, "messages") else 0,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in conversations
        ],
    }


# ============================================
# Cost Tracking
# ============================================


@router.get("/costs", response_model=CostSummaryResponse)
async def get_cost_summary(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    days: int = Query(default=7, le=90),
    tenant_id: str | None = None,
):
    """Get cost summary for the specified period."""
    now = datetime.utcnow()
    period_start = now - timedelta(days=days)

    query = select(LLMCostRecord).where(LLMCostRecord.created_at >= period_start)

    if tenant_id:
        query = query.where(LLMCostRecord.tenant_id == tenant_id)

    result = await db.execute(query)
    records = result.scalars().all()

    total_tokens = sum(r.total_tokens for r in records)
    total_cost = sum(r.cost_usd for r in records)

    # Group by model
    by_model = {}
    for r in records:
        if r.model not in by_model:
            by_model[r.model] = {"tokens": 0, "cost": 0.0}
        by_model[r.model]["tokens"] += r.total_tokens
        by_model[r.model]["cost"] += float(r.cost_usd)

    # Group by tenant
    by_tenant = {}
    for r in records:
        tid = r.tenant_id or "default"
        if tid not in by_tenant:
            by_tenant[tid] = {"tokens": 0, "cost": 0.0}
        by_tenant[tid]["tokens"] += r.total_tokens
        by_tenant[tid]["cost"] += float(r.cost_usd)

    return CostSummaryResponse(
        period_start=period_start,
        period_end=now,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 4),
        by_model=by_model,
        by_tenant=by_tenant,
    )


# ============================================
# Rate Limiting
# ============================================


@router.get("/usage/{tenant_id}", response_model=TenantUsageResponse)
async def get_tenant_usage(tenant_id: str):
    """Get rate limit usage for a tenant."""
    usage = await rate_limiter.get_usage(tenant_id)

    utilization = 0.0
    if usage.tokens_limit > 0:
        utilization = (usage.tokens_used / usage.tokens_limit) * 100

    return TenantUsageResponse(
        tenant_id=tenant_id,
        tokens_used=usage.tokens_used,
        requests_made=usage.requests_made,
        tokens_limit=usage.tokens_limit,
        requests_limit=usage.requests_limit,
        utilization_percent=round(utilization, 2),
    )


@router.post("/usage/{tenant_id}/tier")
async def set_tenant_tier(tenant_id: str, tier: str = Query(..., regex="^(free|standard|premium|enterprise)$")):
    """Set rate limit tier for a tenant."""
    rate_limiter.set_tenant_tier(tenant_id, tier)
    return {"status": "updated", "tenant_id": tenant_id, "tier": tier}


# ============================================
# HITL Queue
# ============================================


@router.get("/hitl/pending")
async def get_pending_approvals():
    """Get all pending HITL requests."""
    pending = await hitl_manager.get_pending()
    return {"count": len(pending), "requests": [r.model_dump() for r in pending]}


@router.get("/hitl/stats")
async def get_hitl_stats():
    """Get HITL queue statistics."""
    pending = await hitl_manager.get_pending()

    by_agent = {}
    by_type = {}

    for req in pending:
        agent = req.agent_name
        action_type = req.action_type

        by_agent[agent] = by_agent.get(agent, 0) + 1
        by_type[action_type] = by_type.get(action_type, 0) + 1

    return {"total_pending": len(pending), "by_agent": by_agent, "by_action_type": by_type}
