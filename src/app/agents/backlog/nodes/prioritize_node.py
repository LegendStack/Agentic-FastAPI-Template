"""
Story Prioritization Node
=========================
Ranks user stories based on ROI (Business Value / Effort).
"""

import logging
from typing import Any

from ..state import BacklogAgentState

logger = logging.getLogger(__name__)


class PrioritizeNode:
    """
    Node that ranks user stories based on calculated ROI.
    ROI = business_value_score / effort_score.
    """

    def __init__(self, config: Any | None = None):
        self.config = config

    async def __call__(self, state: BacklogAgentState) -> dict[str, Any]:
        """
        Sort stories in state by ROI.

        Args:
            state: Current agent state with stories

        Returns:
            State update with sorted stories
        """
        stories = state.get("stories", [])
        if not stories:
            return {}

        logger.info(f"PrioritizeNode: Ranking {len(stories)} stories")

        # Calculate ROI and sort
        # We use a small epsilon for effort_score to avoid division by zero
        sorted_stories = sorted(stories, key=lambda s: s.business_value_score / max(s.effort_score, 1), reverse=True)

        # Update IDs if they were sequential to maintain order visually?
        # Better to keep original IDs but return in new order.

        return {"stories": sorted_stories, "metadata": {**state.get("metadata", {}), "is_prioritized": True}}


# Functional wrapper
async def prioritize_node(state: BacklogAgentState) -> dict[str, Any]:
    node = PrioritizeNode()
    return await node(state)
