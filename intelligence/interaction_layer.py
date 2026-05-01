import json
from pathlib import Path

class InteractionLayer:
    def __init__(self, prefs_path="memory/interaction_prefs.json"):
        import time
        self.prefs_path = Path(prefs_path)
        self.prefs = self._load_prefs()
        self.history = {"verbosity": [], "formality": []}
        
        # Conversation Context Engine
        self.conversation_topic = None
        self.topic_confidence = 0
        self.pending_topic = None
        self.topic_inertia = 0.5 # Adaptive Topic Inertia
        self.conversation_intents = []
        self.last_activity = time.time()
        
        # Soft Context Memory
        self.last_expired_topic = None
        self.expiry_timestamp = 0
        
        self.TOPIC_MAP = {
            "coding": ["code", "project", "backend", "frontend", "api", "database", "python", "bug", "error", "script", "app", "html", "css", "deploy", "build", "create", "develop", "compile"],
            "study": ["read", "study", "exam", "notes", "learn", "chapter", "book", "pdf", "assignment", "homework", "math", "science", "prepare"],
            "system": ["volume", "brightness", "bluetooth", "wifi", "screen", "display", "mute", "lock", "shutdown", "settings"],
            "media": ["music", "song", "spotify", "video", "youtube", "movie", "play", "pause"],
            "schedule": ["reminder", "meeting", "time", "date", "calendar", "alarm", "schedule", "timer", "clock"],
            "web": ["search", "google", "download", "website", "chrome", "browser", "internet"]
        }
        
    def _extract_topic(self, text: str):
        t = text.lower()
        words = t.split()
        word_count = len(words)
        if word_count == 0: return None, 0
        
        counts = {topic: 0 for topic in self.TOPIC_MAP}
        
        for topic, keywords in self.TOPIC_MAP.items():
            for kw in keywords:
                if kw in t:
                    counts[topic] += 1
                    
        # Adaptive Topic Inertia: apply weight to active topic
        if self.conversation_topic and counts.get(self.conversation_topic, 0) > 0:
            counts[self.conversation_topic] += self.topic_inertia
            
        # Choose best topic (Multi-Intent Handling)
        sorted_topics = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        max_topic, score = sorted_topics[0]
        
        if score == 0:
            return None, 0
            
        # Hybrid Confidence Model with Short Sentence Validation
        if word_count <= 5:
            # Short sentence logic
            if score >= 2:
                confidence = 3.0 # HIGH
            elif score >= 1 and max_topic == self.conversation_topic:
                confidence = 2.5 # MEDIUM-STRONG (Matches active)
            elif score >= 1:
                confidence = 2.0 # MEDIUM-WEAK (New topic)
            else:
                confidence = 1.0 # LOW
        else:
            # Long sentence logic
            density = score / word_count
            if score >= 2 and density >= 0.15:
                confidence = 3.0 # HIGH
            elif score >= 1 and density >= 0.10:
                confidence = 2.5 # MEDIUM-STRONG
            elif score >= 1 and density >= 0.05:
                confidence = 2.0 # MEDIUM-WEAK
            else:
                confidence = 1.0 # LOW
            
        return max_topic, confidence
        
    def _load_prefs(self):
        if self.prefs_path.exists():
            try:
                return json.loads(self.prefs_path.read_text())
            except Exception:
                pass
        return {"verbosity": "neutral", "formality": "neutral"}
        
    def _save_prefs(self):
        self.prefs_path.parent.mkdir(exist_ok=True, parents=True)
        self.prefs_path.write_text(json.dumps(self.prefs, indent=2))
        
    def track_interaction(self, user_text: str, jarvis_text: str, jarvis=None):
        import time
        t = user_text.lower()
        length = len(t.split())
        now = time.time()
        updated = False
        
        # Context Engine: Expiry Check (5 mins)
        if now - self.last_activity > 300:
            if self.conversation_topic:
                # Soft Context Memory: Store topic before clearing
                self.last_expired_topic = self.conversation_topic
                self.expiry_timestamp = self.last_activity
                self.conversation_topic = None
                self.topic_confidence = 0
                self.pending_topic = None
                self.conversation_intents.clear()
                updated = True
            
        self.last_activity = now
        
        # Extract and update topic
        extracted_topic, conf = self._extract_topic(t)
        
        # Recovery Logic: If user resumes related topic within 15 mins
        if extracted_topic and self.conversation_topic is None and self.last_expired_topic:
            if now - self.expiry_timestamp < 900: # 15 min window
                # Safe Recovery: Require MEDIUM-STRONG confidence or better to restore (Task 1)
                if extracted_topic == self.last_expired_topic and conf >= 2.5:
                    self.conversation_topic = self.last_expired_topic
                    self.topic_confidence = 3.0 # HIGH on recovery
                    self.topic_inertia = 0.8
                    self.last_expired_topic = None
                    # Clean Context Recovery: history is already cleared on expiry (Task 2)
                    updated = True
        
        if extracted_topic:
            if self.conversation_topic is None:
                self.conversation_topic = extracted_topic
                self.topic_confidence = conf
                self.topic_inertia = 0.8 # Reset inertia on new topic
                updated = True
            elif extracted_topic != self.conversation_topic:
                # Quick-lock if confidence is MEDIUM-STRONG or better
                if self.pending_topic == extracted_topic or conf >= 2.5:
                    self.conversation_topic = extracted_topic
                    self.conversation_intents.clear() # Topic shifted
                    self.topic_confidence = conf
                    self.topic_inertia = 0.8 # Reset inertia on switch
                    self.pending_topic = None
                    updated = True
                else:
                    self.pending_topic = extracted_topic # Soft transition overlap
                    # Dynamic Inertia Decay: FASTER when a topic shift is suspected
                    self.topic_inertia = max(0.1, self.topic_inertia - 0.2)
            else:
                self.topic_confidence = max(self.topic_confidence, conf)
                # Dynamic Inertia Decay: SLOWER when conversation remains consistent
                self.topic_inertia = min(1.0, self.topic_inertia + 0.1)
                self.pending_topic = None
        else:
            self.pending_topic = None
            # Standard Decay
            self.topic_inertia = max(0.2, self.topic_inertia - 0.1)
            
        if self.conversation_topic:
            self.conversation_intents.append(user_text)
            if len(self.conversation_intents) > 4:
                self.conversation_intents.pop(0)
            updated = True # Dirty config to append new intent
        
        # Verbosity Detection
        current_verbosity = "neutral"
        if length <= 3:
            current_verbosity = "short"
        elif length > 15:
            current_verbosity = "detailed"
            
        # Formality Detection
        current_formality = "neutral"
        informal_kws = ["bro", "yaar", "dude", "chill", "hey", "sup", "bhai", "tf", "damn", "shit"]
        formal_kws = ["please", "kindly", "could you", "sir", "assistant", "thank you"]
        
        if any(k in t for k in informal_kws):
            current_formality = "informal"
        elif any(k in t for k in formal_kws):
            current_formality = "formal"
            
        # Update Sliding Window
        self.history["verbosity"].append(current_verbosity)
        self.history["formality"].append(current_formality)
        
        if len(self.history["verbosity"]) > 5:
            self.history["verbosity"].pop(0)
        if len(self.history["formality"]) > 5:
            self.history["formality"].pop(0)
            
        # Check Confidence
        from collections import Counter
        
        verb_count = Counter(self.history["verbosity"])
        if verb_count.most_common(1)[0][1] >= 3:
            dominant_verb = verb_count.most_common(1)[0][0]
            if self.prefs["verbosity"] != dominant_verb:
                self.prefs["verbosity"] = dominant_verb
                updated = True
                
        form_count = Counter(self.history["formality"])
        if form_count.most_common(1)[0][1] >= 3:
            dominant_form = form_count.most_common(1)[0][0]
            if self.prefs["formality"] != dominant_form:
                self.prefs["formality"] = dominant_form
                updated = True
            
        if updated:
            self._save_prefs()
            if jarvis:
                jarvis._config_dirty = True

    def get_prompt_injection(self):
        import time
        parts = []
        
        if self.prefs["verbosity"] != "neutral" or self.prefs["formality"] != "neutral":
            parts.append(
                f"[HUMAN INTERACTION LAYER]\n"
                f"User Verbosity Preference: {self.prefs['verbosity']}\n"
                f"User Formality Preference: {self.prefs['formality']}\n"
            )
            
        if self.conversation_topic and (time.time() - self.last_activity <= 300):
            if self.topic_confidence >= 2.0:
                # Normal Injection (MED/HIGH)
                if self.topic_confidence >= 3.0:
                    conf_str = "HIGH"
                elif self.topic_confidence >= 2.5:
                    conf_str = "MEDIUM-STRONG"
                else:
                    conf_str = "MEDIUM-WEAK"
                
                intents = "\n".join([f"- {i}" for i in self.conversation_intents])
                parts.append(
                    f"[CONVERSATION CONTEXT ENGINE]\n"
                    f"Active Topic: {self.conversation_topic.upper()} (Confidence: {conf_str})\n"
                    f"Recent Intents (use to connect follow-up questions):\n{intents}\n"
                )
            elif self.topic_confidence == 1:
                # Smart Hint Injection: Only if previous context exists to avoid hint noise
                if len(self.conversation_intents) > 1:
                    parts.append(f"[CONVERSATION HINT: Possible Topic: {self.conversation_topic.upper()}]")
            
        return "\n".join(parts)

_layer = None
def get_interaction_layer():
    global _layer
    if not _layer:
        _layer = InteractionLayer()
    return _layer
