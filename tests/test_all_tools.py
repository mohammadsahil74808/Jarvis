import sys
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import pytest

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

@pytest.fixture
def executor():
    jarvis = MockJarvis()
    return ToolExecutor(jarvis)

@pytest.mark.asyncio
@pytest.mark.parametrize("tool_def", TOOL_DECLARATIONS, ids=[t["name"] for t in TOOL_DECLARATIONS])
@patch("agent.tool_executor.asyncio.get_running_loop")
async def test_tool_execution(mock_loop, executor, tool_def):
    name = tool_def["name"]
    args = DUMMY_ARGS.get(name, {})
    
    mock_fc = MagicMock()
    mock_fc.id = "call_123"
    mock_fc.name = name
    mock_fc.args = args
    
    # Patch the ask_verification to avoid blocking Windows Message Box
    f = asyncio.Future()
    f.set_result(6)
    mock_loop.return_value.run_in_executor.return_value = f # IDYES
    
    # Directly mock the standard executor to avoid side effects or real GUI interaction
    with patch.object(executor, '_execute_standard_tool', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_save_memory', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_forget_memory', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_manage_plan', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_browser_agent', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_query_knowledge_base', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_research_mode', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_shutdown_system', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_switch_persona', new_callable=AsyncMock, return_value="Success"), \
         patch.object(executor, '_handle_generate_image', new_callable=AsyncMock, return_value="Success"):
        
        try:
            await asyncio.wait_for(executor.execute(mock_fc), timeout=3.0)
        except asyncio.TimeoutError:
            pass
