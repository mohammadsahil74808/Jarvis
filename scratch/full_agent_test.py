import sys
import os
import time
from pathlib import Path

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from agent.executor import AgentExecutor
    print("[OK] AgentExecutor imported successfully.")
except ImportError as e:
    print(f"[ERROR] ImportError: {e}")
    sys.exit(1)

def test_agent_task():
    print("[START] Starting FULL AGENT TEST: 'Research AI tools and save results to a file'")
    start_time = time.time()
    
    executor = AgentExecutor()
    goal = "Research AI tools and save results to a file called ai_research.txt on Desktop"
    
    def mock_speak(text):
        safe_text = str(text).encode('ascii', 'ignore').decode('ascii')
        print(f"[JARVIS VOICE]: {safe_text}")

    try:
        result = executor.execute(goal, speak=mock_speak)
        end_time = time.time()
        
        print("\n--- TEST RESULTS ---")
        print(f"Result: {result}")
        print(f"Total Execution Time: {end_time - start_time:.2f}s")
        
        # Verify file creation
        desktop = Path.home() / "Desktop"
        possible_files = ["ai_research.txt", "research_results.txt"]
        found = False
        
        for fname in possible_files:
            file_path = desktop / fname
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                print(f"[SUCCESS] File '{fname}' exists on Desktop.")
                print(f"Content Length: {len(content)} characters.")
                if len(content) > 50:
                    print("[SUCCESS] File contains content.")
                found = True
                break
        
        if not found:
            print("[FAILURE] No research file found on Desktop.")
            
    except Exception as e:
        print(f"\n[CRITICAL ERROR TYPE]: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agent_task()
