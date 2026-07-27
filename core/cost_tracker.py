# core/cost_tracker.py
"""
Real-time Token Usage & Cost Tracker for Jarvis models (Gemini, Groq, OpenAI).
Tracks prompt tokens, candidate tokens, total sessions, and estimated cost in USD.
Ported and enhanced from claw-code cost_tracker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Dict, Any


# Model pricing per 1M tokens (Input / Output USD)
MODEL_PRICING: Dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "llama-3.3-70b-versatile": (0.59, 0.79),
}


@dataclass
class UsageRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float


class CostTracker:
    """Thread-safe cost and token tracker for AI agent turns."""

    _instance: CostTracker | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.records: list[UsageRecord] = []

    @classmethod
    def get_instance(cls) -> CostTracker:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def record_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> UsageRecord:
        """Records token usage for a given model call and calculates estimated cost."""
        with self._lock:
            rates = MODEL_PRICING.get(model, (0.10, 0.40))
            input_cost = (prompt_tokens / 1_000_000.0) * rates[0]
            output_cost = (completion_tokens / 1_000_000.0) * rates[1]
            total_cost = input_cost + output_cost

            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_cost_usd += total_cost

            rec = UsageRecord(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost=total_cost
            )
            self.records.append(rec)
            return rec

    def get_summary(self) -> dict[str, Any]:
        """Returns session summary dictionary."""
        with self._lock:
            return {
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
                "total_cost_usd": round(self.total_cost_usd, 6),
                "total_api_calls": len(self.records),
            }

    def reset(self) -> None:
        with self._lock:
            self.total_prompt_tokens = 0
            self.total_completion_tokens = 0
            self.total_cost_usd = 0.0
            self.records.clear()
