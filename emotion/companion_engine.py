import random
from emotion.state_detector import StateDetector
from emotion.conversation_memory import ConversationMemory

class CompanionEngine:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.detector = StateDetector()
        self.memory = ConversationMemory()
        
        self.hinglish_responses = {
            "fatigue": [
                "Sahil, aaj thake lag rahe ho. Kya hua?",
                "Kaafi thak gaye ho lagta hai. Sab theek hai?",
                "Break lena chahoge? Main yahi hoon.",
                "Aap thoda rest kar lo sir, main handle kar lunga."
            ],
            "stress": [
                "Relax sir, ek ek karke solve karte hain.",
                "Tension mat lijiye, main help kar raha hoon.",
                "Thoda deep breath lijiye, we will fix this.",
                "Frustration se kuch nahi hoga Sahil, let's focus."
            ],
            "quiet": [
                "Kaafi chup ho aaj. Mind busy hai kya?",
                "Sab theek hai na Sahil? Main sun raha hoon.",
                "Something on your mind? Share kar sakte ho."
            ],
            "motivation": [
                "Target yaad hai na? Chalo restart karte hain.",
                "Growth ke liye consistency zaroori hai. Let's go!",
                "Sahil, utho! Productivity wait kar rahi hai."
            ],
            "late_night": [
                "Sahil, late ho raha hai. Sona nahi hai?",
                "Raat kafi ho gayi hai, health ka bhi dhyan rakho sir.",
                "Working late again? Don't overwork yourself."
            ]
        }

    def process_interaction(self, user_text: str):
        """Analyze interaction and return a caring response if needed."""
        self.detector.update_timestamp()
        state = self.detector.analyze_input(user_text)
        self.memory.log_state(state)
        
        # Priority logic for caring response
        if state["stress"]:
            return random.choice(self.hinglish_responses["stress"])
        if state["fatigue"]:
            return random.choice(self.hinglish_responses["fatigue"])
        if state["late_night"] and random.random() < 0.3: # Don't annoy every time
            return random.choice(self.hinglish_responses["late_night"])
        
        return None

    def check_proactive(self):
        """Called periodically to check if JARVIS should speak proactively."""
        engagement = self.detector.check_engagement()
        if engagement == "quiet":
            return random.choice(self.hinglish_responses["quiet"])
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
