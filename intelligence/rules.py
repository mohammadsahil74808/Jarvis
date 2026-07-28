# Rules for JARVIS Proactive Intelligence System
import time
from datetime import datetime
from typing import Any

class BaseRule:
    def __init__(self, rule_id: str, priority: int = 1):
        self.rule_id = rule_id
        self.priority = priority # 1 (low) to 10 (high)

    def evaluate(self, system_state, context_state, history) -> Any:
        """
        Evaluates the rule and returns a suggestion dictionary if triggered.
        Returns None if not triggered.
        """
        return None

class HighUsageRule(BaseRule):
    def __init__(self):
        super().__init__("high_usage", priority=7)

    def evaluate(self, system_state, context_state, history):
        if system_state["cpu_percent"] > 85:
            return {
                "text": "Sir, CPU usage is very high. Should I check for heavy processes?",
                "action": "computer_settings list_processes"
            }
        if system_state["ram_percent"] > 90:
            return {
                "text": "Sir, RAM is almost full. Close some background apps?",
                "action": "computer_settings close_heavy_apps"
            }
        return None

class BatteryRule(BaseRule):
    def __init__(self):
        super().__init__("low_battery", priority=9)

    def evaluate(self, system_state, context_state, history):
        bat = system_state["battery"]
        if bat and not bat["power_plugged"] and bat["percent"] < 20:
            return {
                "text": f"Sir, battery is at {bat['percent']}%. Enable saver mode?",
                "action": "computer_settings battery_saver"
            }
        return None

class BreakReminderRule(BaseRule):
    def __init__(self):
        super().__init__("break_reminder", priority=5)
        self.work_start_time = time.time()

    def evaluate(self, system_state, context_state, history):
        # Triggered after 2 hours of activity (not idle)
        uptime = time.time() - self.work_start_time
        if uptime > 7200 and system_state["idle_seconds"] < 60:
            # Check if we already suggested a break in the last hour
            if history.get_cooldown(self.rule_id) > 3600:
                return {
                    "text": "Sir, you've been working for 2 hours. A short break is recommended.",
                    "action": None
                }
        if system_state["idle_seconds"] > 300: # Reset if idle for 5 mins
            self.work_start_time = time.time()
        return None

class CodingWorkflowRule(BaseRule):
    def __init__(self):
        super().__init__("coding_workflow", priority=6)

    def evaluate(self, system_state, context_state, history):
        if context_state["is_coding_mode"] and history.get_cooldown(self.rule_id) > 14400: # 4 hours
             return {
                "text": "Sir, I see you are coding. Shall I start your coding environment (Music + Do Not Disturb)?",
                "action": "workflow_chain coding"
            }
        return None

class InternetRule(BaseRule):
    def __init__(self):
        super().__init__("no_internet", priority=8)

    def evaluate(self, system_state, context_state, history):
        if not system_state["internet"]:
            if history.get_cooldown(self.rule_id) > 1800: # 30 mins
                return {
                    "text": "Sir, internet connection is lost. Would you like me to troubleshoot WiFi?",
                    "action": "computer_settings wifi_troubleshoot"
                }
        return None

class YouTubeDistractionRule(BaseRule):
    def __init__(self):
        super().__init__("youtube_distraction", priority=4)

    def evaluate(self, system_state, context_state, history):
        if "YouTube" in context_state["active_app"] and context_state["hour"] < 17: # Daytime
            if history.get_cooldown(self.rule_id) > 3600:
                return {
                    "text": "Sir, you are watching YouTube during work hours. Focus mode?",
                    "action": None
                }
        return None

class CollegeCommuteRule(BaseRule):
    def __init__(self):
        super().__init__("college_commute", priority=8)

    def evaluate(self, system_state, context_state, history):
        now = datetime.now()
        # Monday-Saturday (0-5)
        if now.weekday() < 6 and now.hour == 7 and 0 <= now.minute <= 30:
            if history.get_cooldown(self.rule_id) > 43200: # 12 hours
                # Simple weather placeholder, in a real system we'd call a weather tool
                return {
                    "text": "Sahil, aaj college jaana hai. Weather clear hai aur travel time lagbhag 35 mins rahega.",
                    "action": None
                }
        return None

class ProjectDeadlineRule(BaseRule):
    def __init__(self):
        super().__init__("project_deadline", priority=10)

    def evaluate(self, system_state, context_state, history):
        # Efficiency: Use preloaded memory from context instead of disk I/O
        mem_str = context_state.get("preloaded_memory", "").lower()
        if not mem_str:
            return None

        if any(kw in mem_str for kw in ["deadline", "submit", "submission"]):
            if history.get_cooldown(self.rule_id) > 86400: # Once a day
                return {
                    "text": "Sahil, aapka ek project deadline pass aa raha hai. Submission ka dhyan rakhiyega.",
                    "action": None
                }
        return None

class GuitarPracticeRule(BaseRule):
    def __init__(self):
        super().__init__("guitar_practice", priority=5)

    def evaluate(self, system_state, context_state, history):
        now = datetime.now()
        # Evening: 6 PM to 10 PM
        if 18 <= now.hour <= 22:
            # Check history for 'guitar' keyword in last 3 days
            if history.get_cooldown(self.rule_id) > 259200: # 3 days
                 # Check if user mentioned guitar recently (simple mock for now)
                 return {
                    "text": "Kaafi din se guitar nahi bajaya Sahil. Shaam ka waqt hai, thodi practice kar lo?",
                    "action": None
                }
        return None

class EmotionalAwarenessRule(BaseRule):
    def __init__(self):
        super().__init__("emotional_awareness", priority=9)

    def evaluate(self, system_state, context_state, history):
        user_status = context_state.get("user_status", {})
        stress_level = user_status.get("stress_level", "normal")
        fatigue = user_status.get("fatigue", False)
        
        # Only trigger proactively if we haven't in the last 2 hours
        if history.get_cooldown(self.rule_id) > 7200:
            if stress_level == "high":
                return {
                    "text": "Sahil, you seem stressed. Would you like me to put on some relaxing music or block notifications for a bit?",
                    "action": None
                }
            if fatigue:
                return {
                    "text": "Sahil, you appear tired. Consider taking a break or wrapping up for the day.",
                    "action": None
                }
        return None

def get_all_rules():
    return [
        HighUsageRule(),
        BatteryRule(),
        BreakReminderRule(),
        CodingWorkflowRule(),
        InternetRule(),
        YouTubeDistractionRule(),
        CollegeCommuteRule(),
        ProjectDeadlineRule(),
        GuitarPracticeRule(),
        EmotionalAwarenessRule()
    ]

