import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.eval.engine import EvalEngine

@pytest.fixture
def mock_llm_service():
    return MagicMock()

@pytest.fixture
def eval_engine(mock_llm_service):
    return EvalEngine(llm_service=mock_llm_service)

@pytest.mark.asyncio
async def test_run_eval(eval_engine):
    # Mocking the 'evaluate' function from ragas
    # We patch it where it's used in app.eval.engine
    mock_result = MagicMock()
    mock_result.to_pandas.return_value = pd.DataFrame([
        {"faithfulness": 0.9, "answer_relevancy": 0.85}
    ])
    
    with patch("src.app.eval.engine.evaluate", return_value=mock_result) as mock_evaluate:
        questions = ["What is FastAPI?"]
        answers = ["FastAPI is a web framework."]
        contexts = [["FastAPI is a modern, fast, web framework for building APIs."]]
        ground_truths = ["FastAPI is a Python web framework."]
        
        results = await eval_engine.run_eval(questions, answers, contexts, ground_truths=ground_truths)
        
        assert len(results) == 1
        assert results[0]["faithfulness"] == 0.9
        assert results[0]["answer_relevancy"] == 0.85
        
        mock_evaluate.assert_called_once()
        # Verify dataset creation (implicitly via mock_evaluate call args)
        args, kwargs = mock_evaluate.call_args
        assert "dataset" in kwargs
        assert len(kwargs["metrics"]) > 0
