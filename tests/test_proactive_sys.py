import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from intelligence.state_monitor import StateMonitor
from intelligence.history import HistoryManager
from intelligence.rules import get_all_rules
from intelligence.proactive_engine import ProactiveEngine

def test_monitor():
    print("Testing StateMonitor...")
    monitor = StateMonitor()
    sys_state = monitor.get_system_state()
    ctx_state = monitor.get_context_state()
    print(f"CPU: {sys_state['cpu_percent']}%")
    print(f"RAM: {sys_state['ram_percent']}%")
    print(f"Battery: {sys_state['battery']}")
    print(f"Active App: {ctx_state['active_app']}")
    print(f"Is Coding: {ctx_state['is_coding_mode']}")
    print("StateMonitor test passed.\n")

def test_history():
    print("Testing HistoryManager...")
    history_file = Path("tmp_proactive_history.json")
    if history_file.exists(): history_file.unlink()
    
    history = HistoryManager(history_file)
    history.log_suggestion("test_rule", "Test suggestion")
    
    cd = history.get_cooldown("test_rule")
    print(f"Cooldown: {cd}s")
    
    history.mark_as_accepted("test_rule")
    rate = history.get_acceptance_rate("test_rule")
    print(f"Acceptance Rate: {rate}")
    
    if history_file.exists(): history_file.unlink()
    print("HistoryManager test passed.\n")

def test_rules():
    print("Testing Rules...")
    rules = get_all_rules()
    sys_state = {
        "cpu_percent": 90,
        "ram_percent": 50,
        "battery": {"percent": 15, "power_plugged": False},
        "internet": True,
        "disk_free_gb": 100,
        "idle_seconds": 0
    }
    ctx_state = {
        "is_coding_mode": True,
        "active_app": "VS Code",
        "hour": 10
    }
    
    # Mock history for cooldowns
    class MockHistory:
        def get_cooldown(self, rule_id): return 9999
        def get_acceptance_rate(self, rule_id): return 0.5
        
    history = MockHistory()
    
    for rule in rules:
        suggestion = rule.evaluate(sys_state, ctx_state, history)
        if suggestion:
            print(f"Rule {rule.rule_id} triggered: {suggestion['text']}")
            if rule.rule_id == "high_usage":
                assert "CPU" in suggestion['text']
            if rule.rule_id == "low_battery":
                assert "battery" in suggestion['text']

    print("Rules test passed.\n")

if __name__ == "__main__":
    try:
        test_monitor()
        test_history()
        test_rules()
        print("ALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"TEST FAILED: {e}")
        sys.exit(1)
