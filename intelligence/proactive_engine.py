import asyncio
import threading
import time
from pathlib import Path
from intelligence.state_monitor import StateMonitor
from intelligence.history import HistoryManager
from intelligence.rules import get_all_rules

class ProactiveEngine:
    def __init__(self, jarvis_live, history_path: Path):
        self.jarvis = jarvis_live
        self.monitor = StateMonitor()
        self.history = HistoryManager(history_path)
        self.rules = get_all_rules()
        
        self.config = {
            "poll_interval": 60, # seconds
            "global_cooldown": 300, # 5 minutes between any two suggestions
            "min_priority": 3,
            "min_acceptance_rate": 0.2
        }
        
        self.running = False
        self._thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._main_loop, daemon=True)
        self._thread.start()
        print("[PROACTIVE] Engine started.")

    def stop(self):
        self.running = False
        print("[PROACTIVE] Engine stopping...")

    def _main_loop(self):
        """Main background loop."""
        while self.running:
            try:
                self._check_and_suggest()
            except Exception as e:
                print(f"[PROACTIVE] Loop Error: {e}")
            
            # Sleep for poll interval
            time.sleep(self.config["poll_interval"])

    def _check_and_suggest(self):
        # 1. Global Cooldown Check
        if self.history.get_global_cooldown() < self.config["global_cooldown"]:
            return

        # 2. Get States
        sys_state = self.monitor.get_system_state()
        ctx_state = self.monitor.get_context_state()

        # 3. Collect Candidates
        candidates = []
        for rule in self.rules:
            # Rule-specific cooldown
            if self.history.get_cooldown(rule.rule_id) < 1800: # 30 min min per rule
                continue
                
            suggestion = rule.evaluate(sys_state, ctx_state, self.history)
            if suggestion:
                # Calculate modified priority based on learning
                acc_rate = self.history.get_acceptance_rate(rule.rule_id)
                
                # If acceptance rate is very low, skip
                if acc_rate < self.config["min_acceptance_rate"]:
                    continue
                    
                score = rule.priority * (0.5 + acc_rate) # Weight by learning
                candidates.append({
                    "rule_id": rule.rule_id,
                    "suggestion": suggestion,
                    "score": score
                })

        if not candidates:
            return

        # 4. Pick best candidate
        best = max(candidates, key=lambda x: x["score"])
        
        # 5. Dispatch
        self._dispatch_suggestion(best)

    def _dispatch_suggestion(self, candidate):
        rule_id = candidate["rule_id"]
        text = candidate["suggestion"]["text"]
        action = candidate["suggestion"].get("action")

        print(f"[PROACTIVE] Suggestion queued: {rule_id}")
        
        # Log it
        self.history.log_suggestion(rule_id, text)

        # Hook into JARVIS
        # We use jarvis.notify() if available, otherwise fallback
        if hasattr(self.jarvis, "notify"):
            self.jarvis.notify(text, voice=True)
        else:
            # Fallback to direct speak and UI show
            if hasattr(self.jarvis, "ui"):
                self.jarvis.ui.show_suggestion(text)
            if hasattr(self.jarvis, "speak"):
                # Avoid speaking if JARVIS is already busy
                if not getattr(self.jarvis, "_is_speaking", False):
                    self.jarvis.speak(f"Sir, {text}")

    def notify_interaction(self, rule_id: str, accepted: bool):
        """Called by JARVIS when a suggestion is accepted or rejected."""
        if accepted:
            self.history.mark_as_accepted(rule_id)
            print(f"[PROACTIVE] Accepted: {rule_id}")
        else:
            self.history.mark_as_rejected(rule_id)
            print(f"[PROACTIVE] Rejected: {rule_id}")
