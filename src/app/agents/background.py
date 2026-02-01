"""
Background agent execution using arq (Redis-backed async task queue).
Enables long-running agent tasks without blocking the API.
"""

import logging
from datetime import datetime
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from ..core.config import settings

logger = logging.getLogger(__name__)


class AgentTaskResult:
    """Result of a background agent task."""

    def __init__(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ):
        self.task_id = task_id
        self.status = status
        self.result = result
        self.error = error
        self.started_at = started_at
        self.completed_at = completed_at


async def get_arq_pool() -> ArqRedis:
    """Get or create the arq Redis connection pool."""
    return await create_pool(RedisSettings(host=settings.REDIS_QUEUE_HOST, port=settings.REDIS_QUEUE_PORT))


async def enqueue_agent_task(
    task_name: str, agent_name: str, input_data: dict[str, Any], thread_id: str | None = None, priority: int = 0
) -> str:
    """
    Enqueue a background agent task.

    Args:
        task_name: Name of the arq task function
        agent_name: Which agent to execute
        input_data: Input to pass to the agent
        thread_id: Optional thread ID for conversation continuity
        priority: Task priority (higher = more urgent)

    Returns:
        Task ID for status tracking
    """
    pool = await get_arq_pool()

    job = await pool.enqueue_job(
        task_name, agent_name=agent_name, input_data=input_data, thread_id=thread_id, _job_try=1
    )

    logger.info(f"Enqueued agent task: {job.job_id} for agent {agent_name}")
    return job.job_id


async def get_task_status(task_id: str) -> AgentTaskResult | None:
    """Get the status of a background agent task."""
    pool = await get_arq_pool()
    job = await pool.job(task_id)

    if not job:
        return None

    job_status = await job.status()
    result = await job.result() if job_status == "complete" else None

    return AgentTaskResult(
        task_id=task_id,
        status=job_status,
        result=result.get("result") if result else None,
        error=result.get("error") if result and "error" in result else None,
    )


# ============================================
# ARQ Worker Tasks (defined in worker module)
# ============================================


async def run_agent_task(
    ctx: dict[str, Any], agent_name: str, input_data: dict[str, Any], thread_id: str | None = None
) -> dict[str, Any]:
    """
    ARQ worker task that executes an agent.
    This runs in the background worker process.
    """
    from ..core.db.database import async_get_db
    from .sample_agent import DocAssistantAgent

    logger.info(f"Executing agent task: {agent_name} with thread {thread_id}")

    try:
        # Get database session from worker context
        async for db in async_get_db():
            if agent_name == "doc_assistant":
                agent = DocAssistantAgent(db)
                result = await agent.chat(
                    user_input=input_data.get("message", ""), thread_id=thread_id or "background-thread"
                )
                return {"result": result, "status": "success"}
            else:
                return {"error": f"Unknown agent: {agent_name}", "status": "failed"}
    except Exception as e:
        logger.error(f"Agent task failed: {e}")
        return {"error": str(e), "status": "failed"}


# Worker class for arq
class WorkerSettings:
    """ARQ worker settings - import this in your worker entrypoint."""

    functions = [run_agent_task]
    redis_settings = RedisSettings(host=settings.REDIS_QUEUE_HOST, port=settings.REDIS_QUEUE_PORT)
    max_jobs = 10
    job_timeout = 300  # 5 minutes max per job
