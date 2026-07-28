# core/state.py

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
        self.system_vitals = {
            "cpu": 0, 
            "ram": 0, 
            "battery": None
        }
        self.active_plan = None
        self.screen_context = None

    def update_vitals(self, cpu: float, ram: float, battery: dict = None):
        self.system_vitals["cpu"] = cpu
        self.system_vitals["ram"] = ram
        if battery is not None:
            self.system_vitals["battery"] = battery

    def update_session(self, key: str, value: str):
        if key in self.session_context:
            self.session_context[key] = value

    def get_session(self, key: str) -> str:
        return self.session_context.get(key)
