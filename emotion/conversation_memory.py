import json
import os
from datetime import datetime

class ConversationMemory:
    def __init__(self, memory_path=None):
        if memory_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.memory_path = os.path.join(base_dir, "memory", "emotional_patterns.json")
        else:
            self.memory_path = memory_path
        
        self.patterns = self.load_patterns()
        self._interaction_count = 0

    def load_patterns(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.get_default_patterns()
        return self.get_default_patterns()

    def save_patterns(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(self.patterns, f, indent=2)

    def log_state(self, state):
        """Logs the current emotional state with a timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = {
            "time": timestamp,
            "state": state
        }
        self.patterns["history"].append(entry)
        
        # Keep history reasonable
        if len(self.patterns["history"]) > 100:
            self.patterns["history"] = self.patterns["history"][-100:]
        
        self.update_stats(state)
        
        # Performance: Only save every 10 interactions or on important change
        self._interaction_count += 1
        if self._interaction_count >= 10:
            self.save_patterns()
            self._interaction_count = 0

    def update_stats(self, state):
        hour = datetime.now().hour
        if state.get("fatigue") or state.get("stress"):
            self.patterns["low_points"][str(hour)] = self.patterns["low_points"].get(str(hour), 0) + 1
        else:
            self.patterns["productive_hours"][str(hour)] = self.patterns["productive_hours"].get(str(hour), 0) + 1

    def get_insights(self):
        """Returns insights about user patterns."""
        if not self.patterns["history"]:
            return "No patterns recorded yet."
        
        # Simple analysis
        best_hour = max(self.patterns["productive_hours"], key=self.patterns["productive_hours"].get, default="N/A")
        worst_hour = max(self.patterns["low_points"], key=self.patterns["low_points"].get, default="N/A")
        
        return f"User is most productive around {best_hour}:00 and tends to feel low around {worst_hour}:00."

    def get_default_patterns(self):
        return {
            "history": [],
            "productive_hours": {},
            "low_points": {},
            "mood_swings": 0
        }
