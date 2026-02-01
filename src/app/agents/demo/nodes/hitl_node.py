"""
HITL Node - Human-in-the-Loop Approval
=======================================
Checks if the response or action requires human approval.
Pauses execution until approval is granted.

This demonstrates the Human-in-the-Loop feature (V1.1).
"""

import logging
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class HITLNode:
    """
    Human-in-the-loop approval node.
    
    Features:
    - Keyword-based approval triggers
    - Approval state management
    - Automatic approval in demo mode
    
    Usage:
        node = HITLNode(config)
        new_state = await node(state)
    """
    
    def __init__(self, config: DemoAgentConfig):
        """Initialize with configuration."""
        self.config = config
        # In-memory approval cache: {request_id -> approved}
        self._approvals: dict[str, bool] = {}
    
    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Check if human approval is needed.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with approval status
        """
        if not self.config.ENABLE_HITL:
            logger.info("HITLNode: HITL disabled, auto-approving")
            return {
                "needs_human_approval": False,
                "human_approved": True,
            }
        
        # Skip if cache hit
        if state.get("cache_hit", False):
            logger.info("HITLNode: Skipping due to cache hit")
            return {}
        
        response = state.get("response", "")
        original_input = state.get("original_input", "")
        thread_id = state.get("thread_id", "default")
        
        # Check if approval is needed
        needs_approval = self._check_approval_needed(original_input, response)
        
        if needs_approval:
            logger.warning(f"HITLNode: Human approval required for thread {thread_id}")
            
            # In a real system, this would pause and wait for approval
            # For demo, we auto-approve after logging
            request_id = f"{thread_id}_{len(self._approvals)}"
            
            # Simulate approval (in production, this would come from UI/API)
            self._approvals[request_id] = True  # Auto-approve for demo
            
            return {
                "needs_human_approval": True,
                "human_approved": self._approvals[request_id],
                "metadata": {
                    **state.get("metadata", {}),
                    "hitl_request_id": request_id,
                    "hitl_triggered_by": self._get_trigger_reason(original_input, response),
                },
            }
        
        return {
            "needs_human_approval": False,
            "human_approved": True,
        }
    
    def _check_approval_needed(self, input_text: str, response: str) -> bool:
        """Check if the input or response triggers HITL."""
        combined_text = (input_text + " " + response).lower()
        
        for keyword in self.config.HITL_KEYWORDS:
            if keyword.lower() in combined_text:
                return True
        
        return False
    
    def _get_trigger_reason(self, input_text: str, response: str) -> str:
        """Identify which keyword triggered HITL."""
        combined_text = (input_text + " " + response).lower()
        
        for keyword in self.config.HITL_KEYWORDS:
            if keyword.lower() in combined_text:
                return f"Keyword detected: '{keyword}'"
        
        return "Unknown trigger"
    
    def approve(self, request_id: str):
        """Manually approve a pending request."""
        self._approvals[request_id] = True
        logger.info(f"HITLNode: Request {request_id} approved")
    
    def reject(self, request_id: str):
        """Reject a pending request."""
        self._approvals[request_id] = False
        logger.info(f"HITLNode: Request {request_id} rejected")
