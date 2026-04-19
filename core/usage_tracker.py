import json
import time
from pathlib import Path
from datetime import datetime

class UsageTracker:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self._save_log([])

    def _load_log(self):
        try:
            if self.log_path.exists():
                return json.loads(self.log_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save_log(self, data):
        self.log_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def log_event(self, event_type: str, event_name: str):
        """
        Logs an event with timestamp.
        event_type: 'app', 'command', 'habit'
        event_name: 'VS Code', 'coding', 'study'
        """
        log = self._load_log()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "name": event_name,
            "hour": datetime.now().hour,
            "weekday": datetime.now().weekday()
        }
        log.append(entry)
        
        # Keep only last 1000 events to stay lightweight
        if len(log) > 1000:
            log = log[-1000:]
            
        self._save_log(log)

tracker = None # Singleton-like instance initialized in main
