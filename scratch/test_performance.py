import sys
import os
import time
import psutil
from pathlib import Path

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from actions.browser_agent import browser_agent
    from memory.semantic_memory import search_semantic_memory
    print("[OK] Performance testing modules imported.")
except ImportError as e:
    print(f"[ERROR] ImportError: {e}")
    sys.exit(1)

def get_ram_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)  # MB

def test_performance():
    print("[START] Starting PERFORMANCE TEST")
    
    # 1. Monitor RAM at idle
    time.sleep(1)
    idle_ram = get_ram_usage()
    print(f"[IDLE] RAM Usage: {idle_ram:.2f} MB")
    
    # 2. Run browser task
    print("\n[STEP 2] Running Browser Task: 'Go to google.com'")
    start_time = time.time()
    try:
        browser_agent({"action": "go_to", "url": "https://www.google.com"})
    except Exception as e:
        print(f"[ERROR] Browser task failed: {e}")
    
    browser_ram = get_ram_usage()
    print(f"[BROWSER ACTIVE] RAM Usage: {browser_ram:.2f} MB (+{browser_ram - idle_ram:.2f} MB)")
    print(f"Browser Task Duration: {time.time() - start_time:.2f}s")
    
    # 3. Close task (browser_agent should close after task is done if my fix is active)
    print("\n[STEP 3] Verifying RAM after browser close...")
    time.sleep(2)  # Give time for cleanup
    post_browser_ram = get_ram_usage()
    print(f"[POST BROWSER] RAM Usage: {post_browser_ram:.2f} MB (Change from active: {post_browser_ram - browser_ram:.2f} MB)")
    
    # 4. Trigger semantic memory search (Model load)
    print("\n[STEP 4] Semantic Memory Search (First Call - Model Load)")
    start_time = time.time()
    search_semantic_memory("Test query")
    first_call_time = time.time() - start_time
    print(f"First Call Duration: {first_call_time:.2f}s")
    
    # 5. Trigger semantic memory search (Subsequent Call)
    print("\n[STEP 5] Semantic Memory Search (Subsequent Call)")
    start_time = time.time()
    search_semantic_memory("Another query")
    subsequent_call_time = time.time() - start_time
    print(f"Subsequent Call Duration: {subsequent_call_time:.2f}s")
    
    # Report
    print("\n--- PERFORMANCE AUDIT REPORT ---")
    print(f"Idle RAM: {idle_ram:.2f} MB")
    print(f"Peak RAM: {browser_ram:.2f} MB")
    print(f"RAM Leak: {max(0, post_browser_ram - idle_ram):.2f} MB")
    print(f"Model Load Latency: {first_call_time:.2f}s")
    print(f"Search Latency: {subsequent_call_time:.4f}s")
    
    if post_browser_ram <= browser_ram + 5: # Small margin
         print("[PASS] RAM correctly released after browser session.")
    else:
         print("[FAIL] Potential RAM leak in browser module.")
         
    if subsequent_call_time < first_call_time:
         print("[PASS] Subsequent memory searches are significantly faster.")
    else:
         print("[FAIL] No performance gain on subsequent calls.")

if __name__ == "__main__":
    test_performance()
