"""Environment-backed configuration for the DeductionDesk agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

AGENT_ROOT = Path(__file__).resolve().parent
load_dotenv(AGENT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://localhost:5432/deductiondesk"
    )
    portal_url: str = os.getenv("PORTAL_URL", "http://localhost:3000").rstrip("/")
    portal_username: str = os.getenv("PORTAL_USERNAME", "supplier_demo")
    portal_password: str = os.getenv("PORTAL_PASSWORD", "glimpse2026")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").lower()
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))

    def __post_init__(self) -> None:
        if self.llm_provider not in ("ollama", "groq"):
            raise ValueError(
                f"LLM_PROVIDER must be 'ollama' or 'groq', got {self.llm_provider!r}"
            )
        if not 0 <= self.confidence_threshold <= 1:
            raise ValueError("CONFIDENCE_THRESHOLD must be between 0 and 1")


settings = Settings()
