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
            "min_acceptance_rate": 0.2,
            "quiet_hours_start": 1,
            "quiet_hours_end": 6,
            "coalesce_time_flush": 300, # 5 minutes
            "escalate_threshold": 3,
            "escalate_cooldown": 600 # 10 minutes
        }
        
        self.running = False
        self._timer = None
        self._coalescer_timer = None
        self.coalesced_events = []
        self._event_counts = {}
        self._escalation_cooldowns = {}

    def start(self):
        if self.running:
            return
        self.running = True
        self._schedule_next()
        print("[PROACTIVE] Engine started.")

    def stop(self):
        self.running = False
        if self._timer:
            self._timer.cancel()
        if self._coalescer_timer:
            self._coalescer_timer.cancel()
        print("[PROACTIVE] Engine stopping...")

    def _schedule_next(self):
        if self._timer:
            self._timer.cancel()
        if self.running:
            self._timer = threading.Timer(self.config["poll_interval"], self._loop_tick)
            self._timer.daemon = True
            self._timer.start()

    def _schedule_coalescer_flush(self):
        if self._coalescer_timer:
            self._coalescer_timer.cancel()
        if self.running and self.coalesced_events:
            self._coalescer_timer = threading.Timer(self.config["coalesce_time_flush"], self._time_flush_coalesced)
            self._coalescer_timer.daemon = True
            self._coalescer_timer.start()

    def _time_flush_coalesced(self):
        try:
            self._flush_coalesced()
        except Exception as e:
            print(f"[PROACTIVE] Coalescer Timer Error: {e}")

    def _loop_tick(self):
        try:
            # Memory Control: Prune event counts and cooldowns older than threshold
            now = time.time()
            self._event_counts = {k: v for k, v in self._event_counts.items() if now - v.get("last_seen", 0) < 3600}
            self._escalation_cooldowns = {k: v for k, v in self._escalation_cooldowns.items() if now - v < self.config.get("escalate_cooldown", 600)}

            self._check_and_suggest()
        except Exception as e:
            print(f"[PROACTIVE] Timer Error: {e}")
        finally:
            self._schedule_next()

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

    def _classify_event(self, text: str, rule_id: str) -> str:
        event_data = self._event_counts.get(rule_id, {"count": 0, "last_seen": 0})
        on_cooldown = (time.time() - self._escalation_cooldowns.get(rule_id, 0) < self.config.get("escalate_cooldown", 600))
        
        if not on_cooldown and event_data["count"] + 1 >= self.config.get("escalate_threshold", 3):
            return "high"

        t = text.lower()
        r = rule_id.lower()
        
        hour = time.localtime().tm_hour
        q_start = self.config.get("quiet_hours_start", 1)
        q_end = self.config.get("quiet_hours_end", 6)
        
        is_quiet = False
        if q_start <= q_end:
            is_quiet = q_start <= hour <= q_end
        else:
            is_quiet = hour >= q_start or hour <= q_end
            
        if is_quiet:
            if "alert" not in t and "error" not in t and "critical" not in t:
                return "low"
                
        if any(k in t or k in r for k in ["alert", "error", "failed", "danger", "urgent", "critical"]):
            return "critical"
        if any(k in t or k in r for k in ["reminder", "meeting", "soon", "important"]):
            return "high"
        if any(k in t or k in r for k in ["tip", "trivia", "suggestion", "might like", "fun fact"]):
            return "low"
            
        return "normal"

    def _dispatch_suggestion(self, candidate):
        rule_id = candidate["rule_id"]
        text = candidate["suggestion"]["text"]
        action = candidate["suggestion"].get("action")

        priority = self._classify_event(text, rule_id)
        
        event_data = self._event_counts.get(rule_id, {"count": 0, "last_seen": 0})
        on_cooldown = (time.time() - self._escalation_cooldowns.get(rule_id, 0) < self.config.get("escalate_cooldown", 600))
        
        if priority == "high" and not on_cooldown and event_data["count"] + 1 >= self.config.get("escalate_threshold", 3):
            text = f"[Escalated] {text}"
            self._event_counts[rule_id] = {"count": 0, "last_seen": time.time()}
            self._escalation_cooldowns[rule_id] = time.time()
        elif priority == "low":
            self._event_counts[rule_id] = {"count": event_data["count"] + 1, "last_seen": time.time()}
        else:
            self._event_counts[rule_id] = {"count": 0, "last_seen": time.time()}

        print(f"[PROACTIVE] Suggestion: {rule_id} [Priority: {priority.upper()}]")
        
        self.history.log_suggestion(rule_id, text)

        if priority == "low":
            self.coalesced_events.append(text)
            self._schedule_coalescer_flush()
            if len(self.coalesced_events) >= 3:
                self._flush_coalesced()
            return

        self._send_to_jarvis(text)

    def _flush_coalesced(self):
        if self._coalescer_timer:
            self._coalescer_timer.cancel()
        if not self.coalesced_events: return
        
        import random
        intros = [
            "Just a few quick updates, sir: ",
            "By the way, here are some minor notes: ",
            "Sir, a couple of things while you have a moment: ",
            "I've gathered a few low-priority updates: "
        ]
        intro = random.choice(intros)
        
        if len(self.coalesced_events) == 1:
            batch_text = intro + self.coalesced_events[0]
        elif len(self.coalesced_events) == 2:
            batch_text = intro + self.coalesced_events[0] + " Additionally, " + self.coalesced_events[1]
        else:
            last = self.coalesced_events.pop()
            batch_text = intro + ", ".join(self.coalesced_events) + f", and finally, {last}"
            
        self.coalesced_events.clear()
        self._send_to_jarvis(batch_text)

    def _send_to_jarvis(self, text):
        if hasattr(self.jarvis, "notify"):
            self.jarvis.notify(text, voice=True)
        else:
            if hasattr(self.jarvis, "ui"):
                self.jarvis.ui.show_suggestion(text)
            if hasattr(self.jarvis, "speak"):
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
