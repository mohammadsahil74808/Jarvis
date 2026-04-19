import json
from pathlib import Path
from datetime import datetime
from collections import Counter

class PredictiveEngine:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.predictive_mode = True

    def set_mode(self, enabled: bool):
        self.predictive_mode = enabled

    def _load_log(self):
        try:
            if self.log_path.exists():
                return json.loads(self.log_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def get_suggestion(self):
        """
        Analyzes usage patterns and returns a suggestion if confidence is high.
        """
        if not self.predictive_mode:
            return None

        log = self._load_log()
        if not log:
            return None

        current_hour = datetime.now().hour
        current_weekday = datetime.now().weekday()

        # 1. Repeated Behavior Detection (Time-based for Apps)
        # Look for apps opened at this specific hour in the past
        app_launches = [
            entry["name"] for entry in log 
            if entry["type"] == "app" and entry["hour"] == current_hour
        ]

        if app_launches:
            counts = Counter(app_launches)
            most_common, count = counts.most_common(1)[0]
            
            # Confidence Threshold: Seen at least 3 times at this hour
            if count >= 3:
                suggestion_id = f"app_launch_{most_common}_{current_hour}"
                if not self._check_already_suggested(suggestion_id):
                    return {
                        "type": "suggestion",
                        "text": f"Usually aap is time {most_common} use karte ho. Kya main use open karu?",
                        "action": f"open_app {most_common}",
                        "confidence": count / len(app_launches)
                    }

        # 2. General Habit Suggestions (Time-based prompts)
        # Morning routine
        if 6 <= current_hour <= 9:
            # Check if already suggested today
            if not self._check_already_suggested("morning_plan"):
                return {
                    "type": "habit",
                    "text": "Good morning Sir! Aaj ka schedule plan karein?",
                    "id": "morning_plan"
                }

        # Night routine
        if current_hour >= 22:
             if not self._check_already_suggested("night_summary"):
                return {
                    "type": "habit",
                    "text": "Sone se pehle aaj ki progress check karu?",
                    "id": "night_summary"
                }

        return None

    def _check_already_suggested(self, suggestion_id: str):
        # Implementation to avoid spamming the same suggestion on the same day
        # For now, let's keep it simple and just use a volatile set in memory
        # In a real app, this should be persisted to avoid spam across restarts
        if not hasattr(self, "_last_suggestions"):
            self._last_suggestions = {}
        
        today = datetime.now().date().isoformat()
        if self._last_suggestions.get(suggestion_id) == today:
            return True
        
        self._last_suggestions[suggestion_id] = today
        return False
