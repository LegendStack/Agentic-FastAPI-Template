import pytest
from src.app.guardrails.pii import PIIGuard
from src.app.guardrails.moderation import Moderator
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def pii_guard():
    return PIIGuard()

@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.chat = AsyncMock()
    return service

@pytest.fixture
def moderator(mock_llm_service):
    return Moderator(llm_service=mock_llm_service)

def test_pii_guard_scan(pii_guard):
    text = "Contact me at john.doe@example.com or call +1-555-555-0199."
    findings = pii_guard.scan(text)
    
    types = [f["type"] for f in findings]
    assert "EMAIL" in types
    assert "PHONE" in types
    assert any("john.doe@example.com" in f["value"] for f in findings)

def test_pii_guard_mask(pii_guard):
    text = "My IP is 192.168.1.1 and my card is 1234-5678-9012-3456."
    masked = pii_guard.mask(text)
    
    assert "192.168.1.1" not in masked
    assert "1234-5678-9012-3456" not in masked
    assert "[MASKED]_IP_ADDRESS" in masked
    assert "[MASKED]_CREDIT_CARD" in masked

@pytest.mark.asyncio
async def test_moderator_hallucination_check(moderator, mock_llm_service):
    # Mock LLM response
    mock_llm_service.chat.return_value = MagicMock(content='{"is_hallucination": false, "reason": "Grounded", "confidence": 0.99}')
    
    context = "LegendStack is a framework."
    answer = "LegendStack is an AI framework."
    
    result = await moderator.check_hallucination(context, answer)
    
    assert "status" in result
    assert result["status"] == "judged"
    assert "content" in result
    mock_llm_service.chat.assert_called_once()

@pytest.mark.asyncio
async def test_moderator_safety_check(moderator):
    result = await moderator.check_safety("Hello world")
    assert result["safe"] is True
    assert result["score"] == 1.0
