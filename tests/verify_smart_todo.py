import sys
import os
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from actions.daily_briefing import get_daily_briefing

def verify_smart_todo():
    print("Testing Smart To-Do Recognition...")
    
    # Run the briefing
    res = get_daily_briefing()
    
    # We know from memory check that tomorrow_plan exists and is "Make changes and customizations to JARVIS"
    expected_part = "Make changes and customizations to JARVIS"
    
    print(f"Briefing Result:\n{res[:400]}...")
    
    if expected_part in res:
        print("\nSUCCESS: Smart To-Do (tomorrow_plan) was found in the briefing!")
    else:
        print("\nFAILURE: Could not find tomorrow_plan in the briefing.")
        sys.exit(1)

if __name__ == "__main__":
    verify_smart_todo()
