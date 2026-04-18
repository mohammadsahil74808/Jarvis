import sys
import os
import json
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import JarvisLive
from actions.open_app import open_app, close_app_by_name

class MockUI:
    def __init__(self):
        self.muted = False
        self.logs = []
    def set_state(self, state): pass
    def write_log(self, text): self.logs.append(text)
    def root(self): pass

def test_context_initialization():
    print("Testing context initialization...")
    ui = MockUI()
    jarvis = JarvisLive(ui)
    assert hasattr(jarvis, "session_context")
    assert jarvis.session_context["last_app"] is None
    print("✅ Context initialization passed.")

def test_context_tracking():
    print("Testing context tracking...")
    ui = MockUI()
    jarvis = JarvisLive(ui)
    
    # Mock a tool call
    class MockFC:
        def __init__(self, name, args):
            self.name = name
            self.args = args
            self.id = "123"

    import asyncio
    
    async def run_test():
        # Simulate open_app call
        fc = MockFC("open_app", {"app_name": "Notepad"})
        await jarvis._execute_tool(fc)
        assert jarvis.session_context["last_app"] == "Notepad"
        assert jarvis.session_context["last_tool"] == "open_app"
        
        # Simulate web_search call
        fc = MockFC("web_search", {"query": "weather in Mumbai"})
        await jarvis._execute_tool(fc)
        assert jarvis.session_context["last_query"] == "weather in Mumbai"
        assert jarvis.session_context["last_action"] == "web_search"
        
        print("✅ Context tracking passed.")

    asyncio.run(run_test())

def test_close_app_functionality():
    print("Testing close_app_by_name...")
    # This test might be system-dependent, but we can verify the logic
    # Try to open notepad and close it
    import subprocess
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(1)
    
    success = close_app_by_name("Notepad")
    print(f"Close success: {success}")
    assert success is True
    print("✅ close_app_by_name passed.")

if __name__ == "__main__":
    try:
        test_context_initialization()
        test_context_tracking()
        if os.name == "nt": # Windows only for notepad test
            test_close_app_functionality()
        print("\nAll short-term context tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
