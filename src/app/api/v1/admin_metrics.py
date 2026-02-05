from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ...core.db.database import async_get_db
from ...models.agentic import Message, Conversation

router = APIRouter(prefix="/admin/metrics", tags=["Admin Metrics"])

class TokenUsageResponse(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_conversations: int
    estimated_cost: float
    total_messages: int

@router.get("/token-usage", response_model=TokenUsageResponse)
async def get_token_usage(db: AsyncSession = Depends(async_get_db)):
    # Calculate costs (approximate defaults for GPT-4o)
    # Input: $2.50 / 1M tokens = $0.0000025 / token
    # Output: $10.00 / 1M tokens = $0.0000100 / token
    INPUT_COST_PER_TOKEN = 0.0000025
    OUTPUT_COST_PER_TOKEN = 0.0000100

    # Aggregate tokens
    token_stats = await db.execute(
        select(
            func.sum(Message.input_tokens),
            func.sum(Message.output_tokens),
            func.count(Message.id)
        )
    )
    input_tokens, output_tokens, total_messages = token_stats.one()
    
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    total_messages = total_messages or 0

    # Count conversations
    conv_stats = await db.execute(select(func.count(Conversation.id)))
    total_conversations = conv_stats.scalar() or 0

    return {
        "total_input_tokens": input_tokens,
        "total_output_tokens": output_tokens,
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "estimated_cost": (input_tokens * INPUT_COST_PER_TOKEN) + (output_tokens * OUTPUT_COST_PER_TOKEN)
    }
