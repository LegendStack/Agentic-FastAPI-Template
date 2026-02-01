"""
PII Scanning and Masking.
=========================
Identifies and masks Personally Identifiable Information (PII)
in LLM inputs and outputs.
"""

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


class PIIGuard:
    """
    Standard PII protector for LegendStack.

    Provides basic masking for:
    - Emails
    - Phone numbers (common formats)
    - IP Addresses
    - Credit Card numbers (basic pattern)
    """

    PATTERNS = {
        "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "PHONE": r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "IP_ADDRESS": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
    }

    def __init__(self, mask_with: str = "[MASKED]"):
        self.mask_with = mask_with
        self._compiled_patterns = {name: re.compile(pattern) for name, pattern in self.PATTERNS.items()}

    def scan(self, text: str) -> List[Dict[str, str]]:
        """
        Scans text for PII and returns a list of findings.
        """
        findings = []
        for name, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                findings.append(
                    {
                        "type": name,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        return findings

    def mask(self, text: str) -> str:
        """
        Masks all identified PII in the text.
        """
        masked_text = text
        # We process in reverse to keep index alignment or just use sub
        for name, pattern in self._compiled_patterns.items():
            masked_text = pattern.sub(f"{self.mask_with}_{name}", masked_text)
        return masked_text


def get_pii_guard() -> PIIGuard:
    """Dependency for obtaining the PIIGuard."""
    return PIIGuard()
