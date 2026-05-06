import random
from emotion.state_detector import StateDetector
from emotion.conversation_memory import ConversationMemory

class CompanionEngine:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.detector = StateDetector()
        self.memory = ConversationMemory()


    def process_interaction(self, user_text: str):
        """Analyze interaction and return a directive for the LLM if an emotional state is detected."""
        self.detector.update_timestamp()
        state = self.detector.analyze_input(user_text)
        self.memory.log_state(state)
        
        # Priority logic for emotional directives
        if state["stress"]:
            return "[EMOTIONAL_STATE: stress detected — respond with genuine care, empathy, and calm tone in Hinglish]"
        
        if state["fatigue"]:
            return "[EMOTIONAL_STATE: fatigue detected — respond with supportive, low-energy comforting tone in Hinglish]"
        
        if state["late_night"] and random.random() < 0.3:
            return "[EMOTIONAL_STATE: late night detected — respond by gently reminding user to rest, in Hinglish]"
        
        return None

    def check_proactive(self):
        """Called periodically to check if JARVIS should speak proactively."""
        engagement = self.detector.check_engagement()
        if engagement == "quiet":
            return "[EMOTIONAL_STATE: user is unusually quiet — check in on them gently in Hinglish]"
        return None

    def get_emotional_context(self):
        """Returns context for the AI prompt."""
        insights = self.memory.get_insights()
        return f"[EMOTIONAL CONTEXT: {insights}]"

# Singleton helper
_engine = None
def get_companion_engine(jarvis=None):
    global _engine
    if _engine is None and jarvis is not None:
        _engine = CompanionEngine(jarvis)
    return _engine
