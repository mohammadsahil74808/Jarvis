import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from actions.reminder import reminder
from actions.daily_briefing import get_daily_briefing

def verify_reminder_fix():
    print("Step 1: Setting a test reminder...")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    res_set = reminder({
        "action": "set",
        "date": tomorrow,
        "time": "10:00",
        "message": "Test Verification Reminder"
    })
    print(f"Set Result: {res_set}")
    
    print("\nStep 2: Listing reminders...")
    res_list = reminder({"action": "list"})
    print(f"List Result:\n{res_list}")
    assert "Test Verification Reminder" in res_list
    
    print("\nStep 3: Checking Daily Briefing...")
    res_briefing = get_daily_briefing()
    print(f"Briefing Result Preview:\n{res_briefing[:500]}...")
    assert "Test Verification Reminder" in res_briefing
    
    print("\nStep 4: Deleting test reminder...")
    res_del = reminder({"action": "delete", "message": "Test Verification Reminder"})
    print(f"Delete Result: {res_del}")
    
    print("\nVERIFICATION SUCCESSFUL!")

if __name__ == "__main__":
    try:
        verify_reminder_fix()
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
        sys.exit(1)
