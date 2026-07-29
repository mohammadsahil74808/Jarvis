import sys
import asyncio
from pathlib import Path
import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_gemini_client, LIVE_MODEL
from main import JarvisLive

# Distinct test cases to test Gemini's tool routing "brain"
TEST_CASES = [
    ("Mute my volume", "computer_settings"),
    ("Who is the president of France?", "web_search"),
    ("Send a whatsapp to John saying hello", "send_message"),
    ("Open Notepad", "open_app"),
    ("What do you see on my screen right now?", "vision_action")
]

class MockRoot:
    def after(self, ms, func, *args): pass

class MockUI:
    def __init__(self):
        self.muted = False
        self.root = MockRoot()
    def set_state(self, state): pass
    def write_log(self, text): pass
    def get_vision_strategy(self): return "none"
    def get_vision_context(self): return ""
    def capture_vision(self): return None

@pytest.fixture(scope="module")
def jarvis_config():
    jarvis = JarvisLive(MockUI())
    return jarvis._build_config()

@pytest.fixture(scope="module")
def gemini_client():
    return get_gemini_client("jarvis")

@pytest.mark.asyncio
@pytest.mark.parametrize("prompt,expected_tool", TEST_CASES, ids=[t[1] for t in TEST_CASES])
async def test_brain_tool_routing(jarvis_config, gemini_client, prompt, expected_tool):
    """
    E2E Brain Test: Sends a natural language prompt to Gemini and asserts 
    that it chooses the correct tool from JARVIS's toolset.
    """
    async with gemini_client.aio.live.connect(model=LIVE_MODEL, config=jarvis_config) as session:
        # Send text to Gemini
        await session.send_client_content(
            turns={"parts": [{"text": prompt}]},
            turn_complete=True
        )
        
        got_tool = None
        timeout = 25.0
        
        try:
            async with asyncio.timeout(timeout):
                async for msg in session.receive():
                    if msg.tool_call:
                        got_tool = msg.tool_call.function_calls[0].name
                        # We must respond to the tool call to keep the session alive
                        await session.send_tool_response(
                            function_responses=[{
                                "id": msg.tool_call.function_calls[0].id,
                                "name": got_tool,
                                "response": {"result": "Dummy success"}
                            }]
                        )
                        break
                    elif msg.server_content and msg.server_content.turn_complete:
                        # Model responded with just text and finished the turn
                        break
        except asyncio.TimeoutError:
            pytest.fail("Model did not respond in time.")
            
        assert got_tool == expected_tool, f"AI chose '{got_tool}' instead of '{expected_tool}'"
