from memory.profile_manager import get_manager

class PersonalContext:
    def __init__(self):
        self.manager = get_manager()

    def get_context_summary(self):
        """Returns a string summary of the user for AI prompting."""
        profile = self.manager.get_profile()
        p = profile["personal_info"]
        
        context = (
            f"User Profile: {p['name']}, {p['age']} years old. "
            f"Lives in {p['location']}, studies {p['course']} ({p['specialization']}) at {p['college']}, {p['college_city']}. "
            f"Skills: {', '.join(profile['skills'])}. "
            f"Interests: {', '.join(profile['interests'])}. "
            f"Personality: {', '.join(profile['personality']['traits'])}. "
            f"Tone Preference: {profile['preferences']['tone']}. "
            f"Routine: {profile['routine']['commute']}. "
        )
        return context

    def get_proactive_prompt(self):
        """Returns a prompt snippet for proactive suggestions."""
        profile = self.manager.get_profile()
        interests = profile.get("interests", [])
        specialization = profile.get("personal_info", {}).get("specialization", "Tech")
        
        return (
            f"Considering I am an {specialization} student interested in {', '.join(interests[:3])}, "
            "suggest something useful or a project idea."
        )

    def detect_language(self, text):
        """Simple heuristic to detect if Hinglish or English is preferred."""
        text = text.lower()
        hindi_common = ["kaise", "kya", "hai", "hu", "kar", "ho", "raha", "aaj", "kal", "theek", "acha"]
        if any(word in text for word in hindi_common):
            return "Hinglish"
        return "English"

    def format_response_vibe(self, text):
        """Wraps response instructions based on profile vibe."""
        profile = self.manager.get_profile()
        vibe = profile["preferences"]["vibe"]
        tone = profile["preferences"]["tone"]
        
        return f"[Vibe: {vibe}, Tone: {tone}] {text}"

# Singleton helper
_context = None
def get_personal_context():
    global _context
    if _context is None:
        _context = PersonalContext()
    return _context
