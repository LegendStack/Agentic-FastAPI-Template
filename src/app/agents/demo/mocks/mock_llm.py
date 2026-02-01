"""
Mock LLM Service
=================
A fake LLM that returns canned responses for testing and demo purposes.
Simulates token counting for cost tracking demonstrations.
"""

import logging
import random
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MockLLMResponse:
    """Simulates an LLM response object."""
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str = "mock-gpt-4o"
    
    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class MockLLM:
    """
    A mock LLM service for demo and testing purposes.
    
    Features:
    - Returns contextual responses based on keywords
    - Simulates token counting for cost tracking
    - Can simulate failures for resilience testing
    
    Usage:
        llm = MockLLM()
        response = await llm.ainvoke("Tell me about LegendStack")
        print(response.content)
    """
    
    # Canned responses based on keywords
    RESPONSES = {
        "legendstack": "LegendStack is an enterprise-ready Agentic AI framework built on FastAPI and LangGraph. It provides production-ready components for building intelligent agents.",
        "features": "The framework includes: RAG pipelines, Graph-RAG, Entity Memory, Semantic Caching, Self-Correction, Safety Guardrails, Rate Limiting, and Observability.",
        "rag": "RAG (Retrieval-Augmented Generation) combines vector search with LLM generation. Our implementation uses pgvector for similarity search and supports reranking.",
        "security": "LegendStack implements Zero-Trust Security with tenant-specific encryption. All data is encrypted at rest using derived keys.",
        "memory": "Entity-Aware Memory allows agents to remember facts about people, projects, and systems across conversation threads using Neo4j.",
        "default": "I understand your question. Based on the available context, I can provide insights on enterprise AI development patterns.",
    }
    
    def __init__(self, failure_rate: float = 0.0):
        """
        Initialize the mock LLM.
        
        Args:
            failure_rate: Probability of simulating a failure (0.0 to 1.0)
        """
        self.failure_rate = failure_rate
        self.call_count = 0
        
    async def ainvoke(self, prompt: str, **kwargs) -> MockLLMResponse:
        """
        Async invoke - simulates an LLM call.
        
        Args:
            prompt: The prompt to send to the "LLM"
            
        Returns:
            MockLLMResponse with content and token counts
        """
        self.call_count += 1
        logger.info(f"MockLLM: Call #{self.call_count}")
        
        # Simulate failures for resilience testing
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            raise Exception("MockLLM: Simulated API failure")
        
        # Find matching response based on keywords
        prompt_lower = prompt.lower()
        response_content = self.RESPONSES["default"]
        
        for keyword, response in self.RESPONSES.items():
            if keyword in prompt_lower:
                response_content = response
                break
        
        # Simulate token counting (rough estimation)
        prompt_tokens = len(prompt.split()) * 2  # ~2 tokens per word
        completion_tokens = len(response_content.split()) * 2
        
        return MockLLMResponse(
            content=response_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    
    async def get_embeddings(self, text: str) -> list[float]:
        """
        Generate mock embeddings for text.
        
        Returns a consistent embedding based on text hash for reproducibility.
        """
        # Create a pseudo-random but deterministic embedding
        hash_val = hash(text.lower())
        random.seed(hash_val)
        embedding = [random.uniform(-1, 1) for _ in range(1536)]
        random.seed()  # Reset random state
        return embedding
