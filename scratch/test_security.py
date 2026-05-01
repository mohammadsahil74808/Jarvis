import sys
import os
from pathlib import Path

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from actions.cmd_control import cmd_control
    from actions.file_manager import file_manager
    print("[OK] Security modules imported successfully.")
except ImportError as e:
    print(f"[ERROR] ImportError: {e}")
    sys.exit(1)

def test_security():
    print("[START] Starting SECURITY TEST")
    
    # 1. "search hello; shutdown"
    print("\n[TEST 1] Task: 'search hello; shutdown'")
    result1 = cmd_control({"task": "search hello; shutdown", "visible": False})
    print(f"Result 1: {result1}")
    
    # 2. "delete all files"
    print("\n[TEST 2] Task: 'delete all files'")
    # Testing file_manager/file_controller
    result2 = file_manager({"action": "delete", "path": "desktop", "name": "*"}, player=None)
    print(f"Result 2: {result2}")
    
    # 3. "remove system files"
    print("\n[TEST 3] Task: 'remove system files'")
    result3 = cmd_control({"task": "remove system files", "visible": False})
    print(f"Result 3: {result3}")

    # Analysis
    print("\n--- SECURITY AUDIT REPORT ---")
    
    if "SECURITY ALERT" in result1 or "UNSAFE" in result1 or "Blocked" in result1:
        print("[PASS] Test 1 (shutdown injection) was blocked/flagged.")
    else:
        print("[FAIL] Test 1 was NOT blocked. Check sanitization.")
        
    if "SECURITY" in result2 or "Are you sure" in result2 or "Blocked" in result2 or "Permission" in result2:
        print("[PASS] Test 2 (mass delete) was blocked/flagged.")
    else:
        print("[FAIL] Test 2 was NOT blocked. Check file_manager safety.")

    if "SECURITY" in result3 or "UNSAFE" in result3 or "Blocked" in result3:
        print("[PASS] Test 3 (system files) was blocked/flagged.")
    else:
        print("[FAIL] Test 3 was NOT blocked.")

if __name__ == "__main__":
    test_security()
