import sys
import os
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import JarvisLive

class MockUI:
    def __init__(self):
        self.muted = False
        self.logs = []
    def set_state(self, state): pass
    def write_log(self, text): 
        print(f"[UI LOG] {text}")
        self.logs.append(text)
    def root(self): pass

def test_manage_plan_logic():
    print("Testing manage_plan tool logic...")
    ui = MockUI()
    jarvis = JarvisLive(ui)
    
    # Mock a tool call
    class MockFC:
        def __init__(self, name, args):
            self.name = name
            self.args = args
            self.id = "123"

    async def run_test():
        # 1. Create plan
        fc = MockFC("manage_plan", {"action": "create", "steps": ["Step A", "Step B", "Step C"]})
        await jarvis._execute_tool(fc)
        assert jarvis.active_plan is not None
        assert len(jarvis.active_plan) == 3
        assert jarvis.active_plan[0]["step"] == "Step A"
        assert jarvis.active_plan[0]["done"] is False
        
        # 2. Update plan (mark step 1 as done)
        fc = MockFC("manage_plan", {"action": "update", "index": 1})
        await jarvis._execute_tool(fc)
        assert jarvis.active_plan[0]["done"] is True
        assert jarvis.active_plan[1]["done"] is False
        
        # 3. Clear plan
        fc = MockFC("manage_plan", {"action": "clear"})
        await jarvis._execute_tool(fc)
        assert jarvis.active_plan is None
        
        print("[PASS] manage_plan tool logic passed.")

    asyncio.run(run_test())

if __name__ == "__main__":
    try:
        test_manage_plan_logic()
        print("\nAll multi-step reasoning tests passed!")
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
