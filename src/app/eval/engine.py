"""
Evaluation Engine.
=================
Automated evaluation for RAG pipelines using Ragas.

Provides metrics for:
- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall
"""

import logging
from typing import Any, Dict, List

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from ..agents.azure_openai import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class EvalEngine:
    """
    Core evaluation engine for LegendStack.

    Usage:
        engine = EvalEngine()
        results = await engine.run_eval(
            questions=["What is LegendStack?"],
            answers=["LegendStack is an agentic framework..."],
            contexts=[["LegendStack is an enterprise-ready template..."]],
            ground_truths=["LegendStack is an agentic AI template built on FastAPI."]
        )
    """

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or get_llm_service()
        self.metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ]

    async def run_eval(
        self,
        questions: List[str],
        answers: List[str],
        contexts: List[List[str]],
        ground_truths: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Runs Ragas evaluation on a set of results.
        """
        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        if ground_truths:
            data["ground_truth"] = ground_truths
            data["reference"] = ground_truths  # Ragas sometimes expects 'reference'

        dataset = Dataset.from_dict(data)

        # Ragas evaluation
        # Note: We need to ensure LLM is passed correctly to metrics if not using defaults
        result = evaluate(
            dataset=dataset,
            metrics=self.metrics,
        )

        return result.to_pandas().to_dict(orient="records")


def get_eval_engine() -> EvalEngine:
    """Dependency for obtaining the EvalEngine."""
    return EvalEngine()
