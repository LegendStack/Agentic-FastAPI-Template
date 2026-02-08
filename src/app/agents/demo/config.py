"""
Demo Agent Configuration
========================
Feature toggles for the LegendDemo Agent. Each feature can be independently
enabled or disabled to help developers understand individual capabilities.
"""

from dataclasses import dataclass, field


@dataclass
class DemoAgentConfig:
    """
    Configuration for the LegendDemo Agent.

    Set USE_MOCKS=True to run without any external dependencies.
    Toggle individual features to learn how each one works.
    """

    # === Core Settings ===
    USE_MOCKS: bool = True  # Use mock services (LLM, Vector, Graph)

    # === Safety & Guardrails ===
    ENABLE_PII_GUARD: bool = True  # Mask PII in input/output
    ENABLE_MODERATION: bool = True  # Check for harmful content

    # === Retrieval ===
    ENABLE_RAG: bool = True  # Vector-based retrieval
    ENABLE_GRAPH_RAG: bool = True  # Neo4j relationship expansion

    # === Intelligence ===
    ENABLE_SEMANTIC_CACHE: bool = True  # Cache similar queries
    ENABLE_ENTITY_MEMORY: bool = True  # Cross-thread entity recall
    ENABLE_MEMORY_SUMMARIZATION: bool = True  # Long conversation handling

    # === Quality ===
    ENABLE_REFLECTOR: bool = True  # Self-correction loop
    REFLECTOR_THRESHOLD: float = 0.7  # Score below which to reflect

    # === Governance ===
    ENABLE_HITL: bool = False  # Human-in-the-loop approval (off by default)
    HITL_KEYWORDS: list = field(default_factory=lambda: ["delete", "execute", "deploy"])

    # === Observability ===
    ENABLE_COST_TRACKING: bool = True  # Track token usage
    ENABLE_TRACING: bool = True  # OpenTelemetry traces

    # === Resilience ===
    ENABLE_CIRCUIT_BREAKER: bool = True
    ENABLE_RETRY: bool = True
    MAX_RETRIES: int = 3

    # === Rate Limiting ===
    ENABLE_RATE_LIMITING: bool = True
    DEFAULT_TIER: str = "premium"  # free, standard, premium, enterprise
