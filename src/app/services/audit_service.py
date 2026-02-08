"""
Audit Service
=============
Handles structured logging of agent actions for compliance and tracking.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agentic import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Service for creating audit log entries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        action: str,
        resource_type: str,
        details: dict[str, Any],
        user_id: str | None = None,
        resource_id: str | None = None,
        thread_id: str | None = None,
        status: str = "SUCCESS",
        tenant_id: str = "default",
    ) -> AuditLog:
        """
        Log an audit event.

        Args:
            action: The action performed (e.g., "JIRA_EXPORT", "CONTENT_GEN")
            resource_type: The type of resource affected (e.g., "ISSUE", "EPIC")
            details: JSON-serializable details about the event
            user_id: ID of the user performing the action
            resource_id: ID of the primary resource (e.g., Jira Key)
            thread_id: Conversation thread ID
            status: Status of the action (SUCCESS/FAILURE)

        Returns:
            The created AuditLog entry
        """
        try:
            audit_entry = AuditLog(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                user_id=str(user_id) if user_id else None,
                thread_id=thread_id,
                status=status,
                tenant_id=tenant_id,
            )
            
            self.db.add(audit_entry)
            await self.db.commit()
            await self.db.refresh(audit_entry)
            
            logger.info(f"AuditService: Logged {action} on {resource_type} {resource_id}")
            return audit_entry
            
        except Exception as e:
            logger.error(f"AuditService: Failed to log event - {e}", exc_info=True)
            # We explicitly do NOT raise here to avoid breaking the main flow
            # if audit logging fails.
            return None
