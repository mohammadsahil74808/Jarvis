import sys
import os
import asyncio
from pathlib import Path

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

async def run_brain_test():
    print("=" * 50)
    print("Initializing E2E Brain Test...")
    
    # Instantiate Jarvis to borrow its configuration building logic
    jarvis = JarvisLive(MockUI())
    config = jarvis._build_config()
    
    client = get_gemini_client("jarvis")
    
    passed = 0
    failed = []
    
    print("Connecting to live Gemini model...")
    print("=" * 50)
    
    for prompt, expected_tool in TEST_CASES:
        print(f"Test Prompt: '{prompt}'")
        print(f"Expecting Tool: {expected_tool}")
        
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            # Send text to Gemini
            await session.send_client_content(
                turns={"parts": [{"text": prompt}]},
                turn_complete=True
            )
            
            # Wait for response
            got_tool = None
            ai_text = []
            timeout = 10.0
            
            try:
                async with asyncio.timeout(timeout):
                    async for msg in session.receive():
                        if msg.server_content and msg.server_content.model_turn:
                            for p in msg.server_content.model_turn.parts:
                                if p.text: ai_text.append(p.text)
                        
                        if msg.tool_call:
                            # Gemini decided to call a tool!
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
                print("[\033[93mTIMEOUT\033[0m] Model did not respond in time.")
                
            if got_tool == expected_tool:
                print(f"Result: [\033[92mPASS\033[0m] AI correctly chose '{got_tool}'")
                passed += 1
            else:
                print(f"Result: [\033[91mFAIL\033[0m] AI chose '{got_tool}' instead of '{expected_tool}'")
                if ai_text:
                    print(f"AI Text Response: {''.join(ai_text).strip()}")
                failed.append((prompt, expected_tool, got_tool))
                
            print("-" * 50)
            await asyncio.sleep(1) # Breathe before next request
            
    print("=" * 50)
    print(f"Brain Tests Passed: {passed}/{len(TEST_CASES)}")
    print("=" * 50)
    
    if failed:
        print("FAILURES:")
        for prompt, exp, got in failed:
            print(f"- Prompt '{prompt}' failed. Expected {exp}, got {got}")

if __name__ == "__main__":
    asyncio.run(run_brain_test())
