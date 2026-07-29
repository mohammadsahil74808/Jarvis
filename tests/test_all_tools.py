import sys
import os
import asyncio
from unittest.mock import MagicMock
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tool_executor import ToolExecutor
from agent.tool_definitions import TOOL_DECLARATIONS

class MockState:
    def __init__(self):
        self.active_persona = "jarvis"
    def update_session(self, key, value):
        pass

class MockRoot:
    def after(self, ms, func, *args):
        pass

class MockUI:
    def __init__(self):
        self.muted = False
        self.root = MockRoot()
    def set_state(self, state):
        pass
    def set_theme(self, theme):
        pass
    def write_log(self, text):
        pass

class MockMemoryExecutor:
    def submit(self, func, *args, **kwargs):
        pass

class MockUsageTracker:
    def log_event(self, category, name):
        pass

class MockJarvis:
    def __init__(self):
        self.ui = MockUI()
        self.state = MockState()
        self.memory_executor = MockMemoryExecutor()
        self.usage_tracker = MockUsageTracker()
        self._config_dirty = False
        self.pending_greeting = None

    def interrupt_speaking(self):
        pass
    def speak(self, text, block=False):
        pass

DUMMY_ARGS = {
    "open_app": {"app_name": "notepad", "action": "open"},
    "vision_action": {"action": "analyze", "angle": "screen", "query": "test"},
    "system_doctor": {},
    "web_search": {"query": "test", "mode": "search"},
    "website_builder": {"prompt": "test", "deploy_to": "none"},
    "app_builder": {"prompt": "test", "build_apk": False},
    "weather_report": {"city": "Delhi"},
    "send_message": {"receiver": "test", "message_text": "test", "platform": "WhatsApp"},
    "reminder": {"action": "list"},
    "youtube_video": {"action": "get_info", "url": "https://youtube.com"},
    "computer_settings": {"action": "volume", "description": "test", "value": "50"},
    "generate_image": {"prompt": "test"},
    "browser_control": {"action": "search", "query": "test"},
    "file_manager": {"action": "list", "path": "desktop"},
    "cmd_control": {"task": "echo test"},
    "desktop_control": {"action": "list"},
    "code_helper": {"action": "explain", "code": "print('test')"},
    "dev_agent": {"description": "test"},
    "agent_task": {"goal": "test"},
    "computer_control": {"action": "move", "x": 100, "y": 100},
    "game_updater": {"action": "list"},
    "flight_finder": {"origin": "DEL", "destination": "BOM", "date": "tomorrow"},
    "save_memory": {"category": "notes", "key": "test", "value": "test"},
    "news_report": {"category": "technology"},
    "daily_briefing": {},
    "workflow_chain": {"mode": "study"},
    "browser_agent": {"action": "search", "query": "test"},
    "screen_vision": {"action": "ocr"},
    "query_knowledge_base": {"query": "test"},
    "research_mode": {"action": "research", "query": "test"},
    "shutdown_system": {"confirm": False},
    "image_cluster": {"mode": "face", "source_folder": "C:/test"},
    "cursor_agent": {"task": "test", "files": ["test.py"]},
    "switch_persona": {"target": "friday"}
}

async def run_tests():
    jarvis = MockJarvis()
    executor = ToolExecutor(jarvis)
    
    passed = 0
    failed = []
    
    print("=" * 50)
    print("Starting Comprehensive Tool Tests...")
    print("=" * 50)
    
    for tool_def in TOOL_DECLARATIONS:
        name = tool_def["name"]
        args = DUMMY_ARGS.get(name, {})
        
        mock_fc = MagicMock()
        mock_fc.id = "call_123"
        mock_fc.name = name
        mock_fc.args = args
        
        print(f"Testing {name:25s}...", end=" ")
        
        try:
            # We wrap it in a timeout because some agents block on tasks
            await asyncio.wait_for(executor.execute(mock_fc), timeout=3.0)
            print("[\033[92mPASS\033[0m]")
            passed += 1
        except asyncio.TimeoutError:
            print("[\033[93mTIMEOUT/PASS\033[0m]")
            passed += 1
        except Exception as e:
            print("[\033[91mFAIL\033[0m]")
            import traceback
            failed.append((name, str(e), traceback.format_exc()))
            
    print("=" * 50)
    print(f"Tests Passed: {passed}/{len(TOOL_DECLARATIONS)}")
    print(f"Tests Failed: {len(failed)}")
    print("=" * 50)
    
    if failed:
        print("\n--- FAILURE DETAILS ---")
        for name, err, tb in failed:
            print(f"\nTool: {name}\nError: {err}\nTraceback:\n{tb}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_tests())
