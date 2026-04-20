import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from actions.file_brain import file_brain

def test_file_brain():
    print("--- Testing FileBrain ---")
    
    # 1. Test Recent Files (Desktop)
    print("1. Testing recent files action...")
    result = file_brain({
        "action": "recent",
        "path": "desktop",
        "count": 3
    })
    print(f"Recent result: {result}")
    
    # 3. Test Copy and Rename actions
    print("\n3. Testing copy and rename logic...")
    test_file = Path.home() / "Desktop" / "jarvis_test_file.txt"
    test_file.write_text("Hello from JARVIS test")
    
    # Rename it
    result = file_brain({
        "action": "rename",
        "path": str(test_file),
        "new_name": "jarvis_renamed.txt"
    })
    print(f"Rename result: {result}")
    
    renamed_file = Path.home() / "Desktop" / "jarvis_renamed.txt"
    if renamed_file.exists():
        print("Success: File renamed.")
        # Cleanup
        renamed_file.unlink()
    
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    test_file_brain()
