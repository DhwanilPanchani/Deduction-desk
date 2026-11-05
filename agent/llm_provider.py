"""Provider abstraction for language model inference backends."""

from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from .config import Settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for deduction classification LLM providers."""

    def __init__(self) -> None:
        self.last_raw_response: str = ""
        self.call_count: int = 0

    @abstractmethod
    def call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        """Call the LLM and return the generated text response."""
        raise NotImplementedError

    def close(self) -> None:
        """Release underlying HTTP resources."""
        pass


class OllamaProvider(LLMProvider):
    """Local Ollama REST API provider (existing behavior, unchanged)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:3b-instruct",
        timeout: float = 90.0,
    ) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

    def call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        self.call_count += 1
        response = self.session.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": temperature},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        self.last_raw_response = response.text
        data = response.json()
        return str(data.get("response", ""))

    def close(self) -> None:
        self.session.close()


class GroqProvider(LLMProvider):
    """Cloud-hosted Groq provider using OpenAI-compatible REST endpoint."""

    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    DEFAULT_MODEL = "qwen/qwen3.8-27b"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        min_interval_seconds: float = 2.6,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is required when using the Groq provider."
            )
        self.model = model or os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self.session = requests.Session()
        self._last_call_time: float = 0.0
        self.rate_limit_429_count: int = 0

    def _wait_for_rate_limit(self) -> None:
        """Enforce request spacing to remain comfortably under Groq free-tier 30 RPM."""
        if self._last_call_time > 0:
            elapsed = time.monotonic() - self._last_call_time
            if elapsed < self.min_interval_seconds:
                sleep_duration = self.min_interval_seconds - elapsed
                time.sleep(sleep_duration)

    def call_llm(self, prompt: str, temperature: float = 0.7) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        retries = 0
        backoff = 2.0

        while True:
            self._wait_for_rate_limit()
            self._last_call_time = time.monotonic()
            self.call_count += 1

            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 429:
                self.rate_limit_429_count += 1
                if retries >= self.max_retries:
                    response.raise_for_status()

                retry_after = response.headers.get("Retry-After")
                sleep_time = backoff
                if retry_after:
                    try:
                        sleep_time = max(float(retry_after), backoff)
                    except ValueError:
                        pass

                logger.warning(
                    "Groq rate limit (429) hit. Backing off for %.2f seconds (attempt %d/%d).",
                    sleep_time,
                    retries + 1,
                    self.max_retries,
                )
                time.sleep(sleep_time)
                backoff *= 2.0
                retries += 1
                continue

            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError(f"Groq returned no choices: {response.text}")

            content = choices[0].get("message", {}).get("content", "")

            # Store an envelope that preserves Groq metadata and includes
            # "response": content for transparent compatibility with pipeline.py
            envelope = dict(data)
            envelope["response"] = content
            self.last_raw_response = json.dumps(envelope)
            return str(content)

    def close(self) -> None:
        self.session.close()


def get_provider(config: Settings | None = None) -> LLMProvider:
    """Factory creating the configured LLM provider."""
    if config is None:
        from .config import settings as default_settings

        config = default_settings

    if config.llm_provider == "groq":
        return GroqProvider(
            api_key=config.groq_api_key,
            model=config.groq_model,
        )
    return OllamaProvider(
        base_url=config.ollama_url,
        model=config.ollama_model,
    )

