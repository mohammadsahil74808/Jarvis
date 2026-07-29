# core/state.py
from typing import Any, Optional

class JarvisState:
    """
    Centralized state container for JarvisLive.
    Extracts mutable session data out of the main class for better modularity.
    """
    def __init__(self):
        self.session_context = {
            "last_app": None, 
            "last_query": None,
            "last_file": None, 
            "last_action": None, 
            "last_tool": None
        }
        self.system_vitals: dict[str, Any] = {
            "cpu": 0.0, 
            "ram": 0.0, 
            "battery": None
        }
        self.active_plan = None
        self.screen_context = None
        self.user_status = {
            "emotion": None,
            "stress_level": "normal",
            "fatigue": False,
            "last_emotion_time": 0.0
        }
        self.active_persona = "jarvis"
        
        try:
            import json
            from core.config import BASE_DIR
            plan_file = BASE_DIR / "memory" / "active_plan.json"
            if plan_file.exists():
                self.active_plan = json.loads(plan_file.read_text(encoding="utf-8"))
        except Exception:
            self.active_plan = None

    def update_vitals(self, cpu: float, ram: float, battery: Optional[dict] = None):
        self.system_vitals["cpu"] = cpu
        self.system_vitals["ram"] = ram
        if battery is not None:
            self.system_vitals["battery"] = battery

    def update_session(self, key: str, value: str):
        if key in self.session_context:
            self.session_context[key] = value

    def get_session(self, key: str) -> Optional[str]:
        return self.session_context.get(key)
        
    def update_user_status(self, key: str, value: Any):
        import time
        if key in self.user_status:
            self.user_status[key] = value
            self.user_status["last_emotion_time"] = time.time()
