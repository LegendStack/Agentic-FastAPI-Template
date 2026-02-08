"""
Input Node - Safety & Guardrails
=================================
First node in the pipeline. Handles:
- PII masking (emails, phones, IPs)
- Content moderation (harmful content check)
- Input validation and sanitization

This demonstrates the Safety Guardrails feature (V3.0).
"""

import logging
import re
from typing import Any

from ..config import DemoAgentConfig
from ..state import DemoAgentState

logger = logging.getLogger(__name__)


class InputNode:
    """
    Input processing node with safety guardrails.

    Features:
    - PII Detection & Masking (emails, phones, IPs, SSNs)
    - Content moderation (checks for harmful keywords)
    - Input sanitization

    Usage:
        node = InputNode(config)
        new_state = await node(state)
    """

    # Regex patterns for PII detection
    PII_PATTERNS = {
        "email": (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_MASKED]"),
        "phone": (r"\b(?:\+?1[-.\s]?)?(?:\(?[0-9]{3}\)?[-.\s]?)?[0-9]{3}[-.\s]?[0-9]{4}\b", "[PHONE_MASKED]"),
        "ip": (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_MASKED]"),
        "ssn": (r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", "[SSN_MASKED]"),
        "credit_card": (r"\b(?:\d{4}[-.\s]?){3}\d{4}\b", "[CC_MASKED]"),
    }

    # Keywords that trigger moderation
    HARMFUL_KEYWORDS = ["hack", "exploit", "attack", "malware", "phishing"]

    def __init__(self, config: DemoAgentConfig):
        """Initialize with configuration."""
        self.config = config

    async def __call__(self, state: DemoAgentState) -> dict[str, Any]:
        """
        Process input through safety guardrails.

        Args:
            state: Current agent state

        Returns:
            Updated state with sanitized input
        """
        original_input = state["messages"][-1]["content"] if state["messages"] else ""
        sanitized = original_input
        metadata = state.get("metadata", {})

        # Store original for audit
        logger.info("InputNode: Processing input through safety guardrails")

        # === PII Masking ===
        if self.config.ENABLE_PII_GUARD:
            sanitized, pii_found = self._mask_pii(sanitized)
            if pii_found:
                metadata["pii_detected"] = True
                logger.info(f"InputNode: Masked PII types: {list(pii_found.keys())}")

        # === Content Moderation ===
        if self.config.ENABLE_MODERATION:
            is_safe, flagged_terms = self._check_moderation(sanitized)
            metadata["moderation_passed"] = is_safe
            if not is_safe:
                logger.warning(f"InputNode: Content flagged for terms: {flagged_terms}")
                # In a real implementation, you might reject or modify the request
                metadata["flagged_terms"] = flagged_terms

        return {
            "original_input": original_input,
            "sanitized_input": sanitized,
            "metadata": metadata,
        }

    def _mask_pii(self, text: str) -> tuple[str, dict[str, int]]:
        """
        Mask PII in text.

        Returns:
            Tuple of (masked_text, dict of PII types found with counts)
        """
        pii_found = {}
        masked = text

        for pii_type, (pattern, replacement) in self.PII_PATTERNS.items():
            matches = re.findall(pattern, masked, re.IGNORECASE)
            if matches:
                pii_found[pii_type] = len(matches)
                masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)

        return masked, pii_found

    def _check_moderation(self, text: str) -> tuple[bool, list[str]]:
        """
        Check text for harmful content.

        Returns:
            Tuple of (is_safe, list of flagged terms)
        """
        text_lower = text.lower()
        flagged = [term for term in self.HARMFUL_KEYWORDS if term in text_lower]
        return len(flagged) == 0, flagged
