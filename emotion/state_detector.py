import time
from datetime import datetime

class StateDetector:
    def __init__(self):
        self.last_interaction_time = time.time()
        self.consecutive_short_inputs = 0
        self.fatigue_keywords = ["tired", "exhausted", "sleepy", "neend", "thak", "preshan", "boring"]
        self.stress_keywords = ["stress", "tension", "dimag kharab", "frustrated", "gussa", "error", "nahi ho raha"]

    def analyze_input(self, text: str):
        """Analyze text for emotional markers."""
        text = text.lower()
        state = {
            "fatigue": False,
            "stress": False,
            "low_energy": False,
            "late_night": False
        }

        # 1. Keyword check
        if any(word in text for word in self.fatigue_keywords):
            state["fatigue"] = True
        
        if any(word in text for word in self.stress_keywords):
            state["stress"] = True

        # 2. Input pattern check
        if len(text.split()) < 3:
            self.consecutive_short_inputs += 1
        else:
            self.consecutive_short_inputs = 0
        
        if self.consecutive_short_inputs >= 5:
            state["low_energy"] = True

        # 3. Time check
        hour = datetime.now().hour
        if hour >= 23 or hour <= 4:
            state["late_night"] = True

        return state

    def check_engagement(self):
        """Check if user has been quiet for too long."""
        idle_time = time.time() - self.last_interaction_time
        if 1800 < idle_time < 3600: # 30-60 mins
            return "quiet"
        return "normal"

    def update_timestamp(self):
        self.last_interaction_time = time.time()
