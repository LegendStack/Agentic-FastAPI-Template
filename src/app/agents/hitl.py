"""
Human-in-the-Loop (HITL) patterns for agent workflows.
Provides interrupt, review, and resume capabilities for sensitive operations.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HITLStatus(str, Enum):
    """Status of a Human-in-the-Loop request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    MODIFIED = "modified"


class HITLRequest(BaseModel):
    """A request for human review/approval."""

    id: str
    thread_id: str
    agent_name: str
    action_type: str
    action_description: str
    proposed_action: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    status: HITLStatus = HITLStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    reviewer_notes: str | None = None
    modified_action: dict[str, Any] | None = None


class HITLManager:
    """
    Manages Human-in-the-Loop requests for agent workflows.

    Usage in LangGraph:
        @node
        async def sensitive_action(state):
            if requires_approval(state):
                request = await hitl_manager.request_approval(
                    thread_id=state["thread_id"],
                    action_type="data_modification",
                    proposed_action={"delete_count": 100}
                )
                # Agent pauses here - state is persisted
                return {"hitl_request_id": request.id, "status": "awaiting_approval"}
    """

    def __init__(self):
        # In production, this would be backed by a database
        self._pending_requests: dict[str, HITLRequest] = {}

    async def request_approval(
        self,
        thread_id: str,
        agent_name: str,
        action_type: str,
        action_description: str,
        proposed_action: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> HITLRequest:
        """
        Create an approval request that pauses the agent workflow.
        The agent should persist its state and wait for human review.
        """
        import uuid

        request = HITLRequest(
            id=f"hitl_{uuid.uuid4().hex[:8]}",
            thread_id=thread_id,
            agent_name=agent_name,
            action_type=action_type,
            action_description=action_description,
            proposed_action=proposed_action,
            context=context or {},
        )

        self._pending_requests[request.id] = request
        logger.info(f"HITL request created: {request.id} for thread {thread_id}")

        return request

    async def get_pending_requests(
        self, thread_id: str | None = None, agent_name: str | None = None
    ) -> list[HITLRequest]:
        """Get all pending HITL requests, optionally filtered."""
        requests = list(self._pending_requests.values())

        if thread_id:
            requests = [r for r in requests if r.thread_id == thread_id]
        if agent_name:
            requests = [r for r in requests if r.agent_name == agent_name]

        return [r for r in requests if r.status == HITLStatus.PENDING]

    async def approve(self, request_id: str, reviewer: str, notes: str | None = None) -> HITLRequest:
        """Approve a pending request, allowing the agent to resume."""
        if request_id not in self._pending_requests:
            raise ValueError(f"HITL request {request_id} not found")

        request = self._pending_requests[request_id]
        request.status = HITLStatus.APPROVED
        request.reviewed_at = datetime.utcnow()
        request.reviewed_by = reviewer
        request.reviewer_notes = notes

        logger.info(f"HITL request {request_id} approved by {reviewer}")
        return request

    async def reject(self, request_id: str, reviewer: str, reason: str) -> HITLRequest:
        """Reject a pending request, stopping the agent action."""
        if request_id not in self._pending_requests:
            raise ValueError(f"HITL request {request_id} not found")

        request = self._pending_requests[request_id]
        request.status = HITLStatus.REJECTED
        request.reviewed_at = datetime.utcnow()
        request.reviewed_by = reviewer
        request.reviewer_notes = reason

        logger.info(f"HITL request {request_id} rejected by {reviewer}: {reason}")
        return request

    async def modify_and_approve(
        self, request_id: str, reviewer: str, modified_action: dict[str, Any], notes: str | None = None
    ) -> HITLRequest:
        """Modify the proposed action and approve it."""
        if request_id not in self._pending_requests:
            raise ValueError(f"HITL request {request_id} not found")

        request = self._pending_requests[request_id]
        request.status = HITLStatus.MODIFIED
        request.reviewed_at = datetime.utcnow()
        request.reviewed_by = reviewer
        request.reviewer_notes = notes
        request.modified_action = modified_action

        logger.info(f"HITL request {request_id} modified and approved by {reviewer}")
        return request

    async def get_request_status(self, request_id: str) -> HITLRequest | None:
        """Check the status of a HITL request."""
        return self._pending_requests.get(request_id)


# Global HITL manager instance
hitl_manager = HITLManager()
