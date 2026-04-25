import json
import time
from pathlib import Path
from datetime import datetime

class HistoryManager:
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"logs": [], "stats": {}}

    def _save(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def log_suggestion(self, rule_id: str, suggestion_text: str, status: str = "queued"):
        """
        Logs a suggestion. status can be 'queued', 'accepted', 'rejected'.
        """
        entry = {
            "timestamp": time.time(),
            "date": datetime.now().isoformat(),
            "rule_id": rule_id,
            "text": suggestion_text,
            "status": status
        }
        self.data["logs"].append(entry)
        
        # Update stats for learning
        if rule_id not in self.data["stats"]:
            self.data["stats"][rule_id] = {"accepted": 0, "rejected": 0, "total": 0}
        
        self.data["stats"][rule_id]["total"] += 1
        if status == "accepted":
            self.data["stats"][rule_id]["accepted"] += 1
        elif status == "rejected":
            self.data["stats"][rule_id]["rejected"] += 1

        # Keep logs manageable
        if len(self.data["logs"]) > 500:
            self.data["logs"] = self.data["logs"][-500:]
            
        self._save()

    def get_cooldown(self, rule_id: str):
        """Returns the time since the last suggestion for this rule."""
        last_time = 0
        for log in reversed(self.data["logs"]):
            if log["rule_id"] == rule_id:
                last_time = log["timestamp"]
                break
        
        if last_time == 0:
            return 999999 # Long time ago
        return time.time() - last_time

    def get_global_cooldown(self):
        """Returns the time since any suggestion was last made."""
        if not self.data["logs"]:
            return 999999
        return time.time() - self.data["logs"][-1]["timestamp"]

    def get_acceptance_rate(self, rule_id: str):
        """Returns the acceptance rate for a rule (0.0 to 1.0)."""
        stats = self.data["stats"].get(rule_id)
        if not stats or stats["total"] == 0:
            return 0.5 # Default neutral
        return stats["accepted"] / stats["total"]

    def mark_as_accepted(self, rule_id: str):
        self.log_suggestion(rule_id, "", status="accepted")

    def mark_as_rejected(self, rule_id: str):
        self.log_suggestion(rule_id, "", status="rejected")
