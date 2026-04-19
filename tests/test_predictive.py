import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from core.usage_tracker import UsageTracker
from core.predictive_engine import PredictiveEngine

def test_prediction():
    print("--- STARTING TEST ---")
    log_path = BASE_DIR / "tmp_usage_log.json"
    if log_path.exists(): log_path.unlink()
        
    tracker = UsageTracker(log_path)
    engine = PredictiveEngine(log_path)
    
    # 1. Test App Suggestion logic
    print("Step 1: Logging events...")
    for _ in range(5):
        tracker.log_event("app", "VS Code")
        
    print("Step 2: Getting first suggestion...")
    s1 = engine.get_suggestion()
    if s1:
        print(f"Result 1: {s1['text']}")
    else:
        print("Result 1: NONE")

    print("Step 3: Getting second suggestion (should be NONE due to spam protection)...")
    s2 = engine.get_suggestion()
    if s2:
        print(f"Result 2: {s2['text']}")
    else:
        print("Result 2: NONE (CORRECT)")

    if s1 and not s2:
        print("TEST PASSED")
    else:
        print("TEST FAILED")

    if log_path.exists(): log_path.unlink()

if __name__ == "__main__":
    test_prediction()
