import sys
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.executor import AgentExecutor
from memory.semantic_memory import add_semantic_memory

def test_stability():
    print("[START] Starting STABILITY TEST (5 consecutive tasks)")
    executor = AgentExecutor()
    
    tasks = [
        "What is the capital of France? Save result to capital.txt",
        "Who founded SpaceX? Save result to spacex.txt",
        "What is 2+2? Save result to math.txt",
        "Weather in Tokyo? Save result to weather.txt",
        "Latest news on AI? Save result to news.txt"
    ]
    
    for i, goal in enumerate(tasks, 1):
        print(f"\n--- TASK {i}: {goal} ---")
        try:
            start = time.time()
            result = executor.execute(goal)
            duration = time.time() - start
            
            print(f"[OK] Task {i} completed in {duration:.2f}s")
            
            # Store to memory
            add_semantic_memory(f"Stability test task {i} result: {result}")
            print(f"[OK] Memory stored for task {i}")
            
        except Exception as e:
            print(f"[FAIL] Task {i} crashed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
            
    print("\n[SUCCESS] Stability test completed with 0 crashes.")

if __name__ == "__main__":
    test_stability()
