"""Unit tests for LLM providers and provider-agnostic classifier."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from agent.config import Settings
from agent.llm_classifier import LLMClassifier
from agent.llm_provider import GroqProvider, LLMProvider, OllamaProvider, get_provider
from agent.models import Deduction


class DummyProvider(LLMProvider):
    def __init__(self, responses: list[str]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.prompts: list[str] = []

    def call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        self.prompts.append(prompt)
        res = self.responses.pop(0)
        self.last_raw_response = json.dumps({"response": res, "provider": "dummy"})
        return res


def make_deduction(dtype: str = "shortage") -> Deduction:
    return Deduction(
        id=101,
        retailer="Target",
        type=dtype,
        claimed_amount=150.0,
        status="pending",
        retailer_notes="Hi team, please review shortage on PO-1234",
        invoice_id=202,
    )


def test_ollama_provider_call() -> None:
    provider = OllamaProvider(base_url="http://mock-ollama:11434", model="test-model")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps({"response": '{"is_valid": true, "reasoning": "matches"}'})
    mock_resp.json.return_value = {"response": '{"is_valid": true, "reasoning": "matches"}'}

    with patch.object(provider.session, "post", return_value=mock_resp) as mock_post:
        output = provider.call_llm("test prompt", temperature=0.7)
        assert output == '{"is_valid": true, "reasoning": "matches"}'
        assert provider.last_raw_response == mock_resp.text
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://mock-ollama:11434/api/generate"
        assert kwargs["json"]["model"] == "test-model"
        assert kwargs["json"]["options"]["temperature"] == 0.7


def test_groq_provider_missing_key() -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            GroqProvider(api_key="")


def test_groq_provider_success() -> None:
    provider = GroqProvider(api_key="mock_key", model="qwen/qwen3.8-27b", min_interval_seconds=0.0)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    expected_content = '{"is_valid": false, "reasoning": "mismatch"}'
    mock_resp.json.return_value = {
        "id": "chatcmpl-123",
        "choices": [{"message": {"content": expected_content}}],
    }

    with patch.object(provider.session, "post", return_value=mock_resp) as mock_post:
        output = provider.call_llm("prompt", temperature=0.7)
        assert output == expected_content
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.groq.com/openai/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer mock_key"
        assert kwargs["json"]["model"] == "qwen/qwen3.8-27b"
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        # Check backward-compatible envelope in last_raw_response
        envelope = json.loads(provider.last_raw_response)
        assert envelope["response"] == expected_content


def test_groq_provider_rate_limit_spacing() -> None:
    provider = GroqProvider(api_key="mock_key", min_interval_seconds=0.1)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"is_valid": true, "reasoning": "ok"}'}}],
    }

    with patch.object(provider.session, "post", return_value=mock_resp):
        t0 = time.monotonic()
        provider.call_llm("call 1")
        provider.call_llm("call 2")
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.09  # Spaced by ~0.1s minimum


def test_groq_provider_429_backoff_and_retry() -> None:
    provider = GroqProvider(api_key="mock_key", min_interval_seconds=0.0, max_retries=3)

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "0.01"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": '{"is_valid": true, "reasoning": "recovered"}'}}],
    }

    with patch.object(provider.session, "post", side_effect=[resp_429, resp_429, resp_200]) as mock_post:
        with patch("time.sleep") as mock_sleep:
            output = provider.call_llm("test")
            assert output == '{"is_valid": true, "reasoning": "recovered"}'
            assert mock_post.call_count == 3
            assert mock_sleep.call_count == 2


def test_groq_provider_429_exhausted_retries() -> None:
    provider = GroqProvider(api_key="mock_key", min_interval_seconds=0.0, max_retries=2)

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {}
    resp_429.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")

    with patch.object(provider.session, "post", return_value=resp_429):
        with patch("time.sleep"):
            with pytest.raises(requests.HTTPError, match="429"):
                provider.call_llm("test")


def test_classifier_self_consistency_agreement_unanimous() -> None:
    decision_json = '{"is_valid": true, "reasoning": "evidence matches"}'
    dummy = DummyProvider([decision_json, decision_json, decision_json])
    cfg = Settings(llm_provider="ollama")
    classifier = LLMClassifier(config=cfg, provider=dummy)

    deduction = make_deduction("shortage")
    context = {"claimed_qty": 5, "invoiced_qty": 100, "delivered_qty": 95}
    result = classifier.classify(deduction, context)

    assert result.resolved is True
    assert result.is_valid is True
    assert result.confidence == 1.0
    assert result.agreement_rate == 1.0
    assert result.votes == [True, True, True]
    assert len(result.raw_responses) == 3


def test_classifier_self_consistency_split_vote() -> None:
    dummy = DummyProvider([
        '{"is_valid": false, "reasoning": "first vote"}',
        '{"is_valid": true, "reasoning": "second vote"}',
        '{"is_valid": true, "reasoning": "third vote"}',
    ])
    cfg = Settings(llm_provider="groq")
    classifier = LLMClassifier(config=cfg, provider=dummy)

    deduction = make_deduction("shortage")
    context = {"claimed_qty": 5, "invoiced_qty": 100, "delivered_qty": 95}
    result = classifier.classify(deduction, context)

    assert result.resolved is True
    assert result.is_valid is True
    assert pytest.approx(result.agreement_rate, 0.01) == 2 / 3
    assert result.votes == [False, True, True]
    assert result.reasoning == "second vote"


def test_classifier_retry_on_malformed_json() -> None:
    dummy = DummyProvider([
        "Malformed plain text with no json",
        '{"is_valid": true, "reasoning": "fixed on attempt 2"}',
        '{"is_valid": true, "reasoning": "vote 2"}',
        '{"is_valid": true, "reasoning": "vote 3"}',
    ])
    cfg = Settings(llm_provider="ollama")
    classifier = LLMClassifier(config=cfg, provider=dummy)

    deduction = make_deduction("shortage")
    context = {"claimed_qty": 5, "invoiced_qty": 100, "delivered_qty": 95}
    result = classifier.classify(deduction, context)

    assert result.resolved is True
    assert result.is_valid is True
    assert result.votes == [True, True, True]


def test_get_provider_factory() -> None:
    cfg_ollama = Settings(llm_provider="ollama", ollama_url="http://localhost:11434")
    prov1 = get_provider(cfg_ollama)
    assert isinstance(prov1, OllamaProvider)

    cfg_groq = Settings(llm_provider="groq", groq_api_key="dummy_key", groq_model="qwen/qwen3.8-27b")
    prov2 = get_provider(cfg_groq)
    assert isinstance(prov2, GroqProvider)

