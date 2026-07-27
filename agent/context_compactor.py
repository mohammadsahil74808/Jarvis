# agent/context_compactor.py
"""
Context Window Manager & Transcript Compactor for Jarvis.
Ported and adapted from claw-code runtime context compaction.
Summarizes older turns and maintains token bounds without losing key facts.
"""
from __future__ import annotations

from typing import List, Dict, Any


class ContextCompactor:
    """Manages conversation context window, compaction, and summarization."""

    def __init__(self, max_history_turns: int = 20, max_token_estimate: int = 30000):
        self.max_history_turns = max_history_turns
        self.max_token_estimate = max_token_estimate

    def should_compact(self, history: List[Dict[str, Any]]) -> bool:
        """Determines whether context needs compaction based on length or estimated tokens."""
        if len(history) > self.max_history_turns:
            return True
        total_chars = sum(len(str(turn.get("content", ""))) for turn in history)
        # Rough heuristic: 1 token ~ 4 characters
        return (total_chars / 4) > self.max_token_estimate

    def compact(self, history: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], str]:
        """
        Compacts long conversation history by preserving system prompts & recent turns,
        while returning a summary of pruned older turns.
        """
        if not self.should_compact(history):
            return history, ""

        # Keep system prompt if present
        system_turns = [t for t in history if t.get("role") == "system"]
        user_assistant_turns = [t for t in history if t.get("role") != "system"]

        # Keep last 10 turns
        keep_count = min(10, len(user_assistant_turns))
        pruned_turns = user_assistant_turns[:-keep_count]
        recent_turns = user_assistant_turns[-keep_count:]

        # Create concise summary of pruned turns
        summary_lines = []
        for turn in pruned_turns:
            role = turn.get("role", "user").upper()
            content = str(turn.get("content", ""))[:150]
            summary_lines.append(f"{role}: {content}...")

        summary_text = "[CONVERSATION COMPACTED SUMMARY]\n" + "\n".join(summary_lines)
        summary_turn = {"role": "system", "content": summary_text}

        compacted_history = system_turns + [summary_turn] + recent_turns
        return compacted_history, summary_text
