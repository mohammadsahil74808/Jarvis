import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Mocking the action imports BEFORE importing workflow_chains to avoid actual calls
# But workflow_chains imports them as 'from actions.xxx import xxx'.
# So we need to patch those specific imports.

def test_workflows():
    print("--- STARTING WORKFLOW VERIFICATION ---")
    
    with patch("actions.workflow_chains.open_app") as mock_open, \
         patch("actions.workflow_chains.close_app_by_name") as mock_close, \
         patch("actions.workflow_chains.computer_settings") as mock_settings, \
         patch("actions.workflow_chains.reminder") as mock_reminder:
         
        from actions.workflow_chains import workflow_chains
        
        # Test Study Mode
        print("Testing Study Mode...")
        workflow_chains({"mode": "study"})
        
        # Expected calls for Study Mode:
        # 1. open_app(Obsidian)
        # 2. open_app(edge)
        # 3. close_app_by_name(Discord, Spotify, Steam)
        # 4. computer_settings(volume_set, 20)
        # 5. reminder(...)
        
        app_calls = [call.args[0]["app_name"] for call in mock_open.call_args_list]
        print(f"App calls: {app_calls}")
        if "Obsidian" in app_calls and "edge" in app_calls:
            print("✅ Study Mode: open_app calls correct.")
        else:
            print("❌ Study Mode: open_app calls incorrect.")
            
        close_calls = [call.args[0] for call in mock_close.call_args_list]
        print(f"Close calls: {close_calls}")
        if "Discord" in close_calls:
            print("✅ Study Mode: close_app_by_name calls correct.")
        else:
            print("❌ Study Mode: close_app_by_name calls incorrect.")

        print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    test_workflows()
