import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from actions.cmd_control import cmd_control

def test_cmd_safety():
    print("Starting Command Control Safety Test...")
    
    # 1. Test Blocked command (destructive)
    print("\n[Test 1] Destructive command (del)...")
    res1 = cmd_control({"command": "del test.txt"})
    print(f"Result: {res1}")
    if "SECURITY ALERT" in res1:
        print("SUCCESS: Destructive command blocked without confirmation.")
    else:
        print("FAILURE: Destructive command NOT blocked!")

    # 2. Test Blocked command with confirmation
    print("\n[Test 2] Destructive command with confirmation...")
    # Note: We won't actually execute it because we don't want to break anything, 
    # but we check if it passes the check.
    # Actually, cmd_control will try to run it. 
    # Let's use a non-existent file to be safe.
    res2 = cmd_control({"command": "del non_existent_file_jarvis_test.txt", "confirm": True})
    print(f"Result: {res2}")
    if "SECURITY ALERT" not in res2:
        print("SUCCESS: Confirmation bypasses security alert.")
    else:
        print("FAILURE: Confirmation did NOT bypass alert!")

    # 3. Test Allowlisted command
    print("\n[Test 3] Allowlisted command (ipconfig)...")
    res3 = cmd_control({"command": "ipconfig"})
    if "SECURITY ALERT" not in res3 and "Blocked" not in res3:
        print("SUCCESS: Allowlisted command permitted.")
    else:
        print(f"FAILURE: Allowlisted command blocked! Result: {res3}")

    # 4. Test Prohibited pattern (eval)
    print("\n[Test 4] Prohibited pattern (eval)...")
    res4 = cmd_control({"command": "echo eval(1+1)"})
    if "Prohibited pattern" in res4:
        print("SUCCESS: Prohibited pattern blocked.")
    else:
        print(f"FAILURE: Prohibited pattern NOT blocked! Result: {res4}")

if __name__ == "__main__":
    test_cmd_safety()
