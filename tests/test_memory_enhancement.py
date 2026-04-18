import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from memory.memory_manager import (
    load_memory, save_memory, update_memory, 
    format_memory_for_prompt, extract_memory, should_extract_memory
)

def test_config_loading():
    print("Testing config loading...")
    memory = load_memory()
    assert isinstance(memory, dict)
    assert "patterns" in memory
    print("✅ Config loading passed.")

def test_persistence():
    print("Testing persistence...")
    test_data = {"patterns": {"test_habit": {"value": "Always drinks coffee at 8 AM"}}}
    update_memory(test_data)
    
    memory = load_memory()
    assert memory["patterns"]["test_habit"]["value"] == "Always drinks coffee at 8 AM"
    print("✅ Persistence passed.")

def test_formatting():
    print("Testing formatting...")
    memory = {
        "identity": {"name": {"value": "Sahil"}},
        "patterns": {"coding_habit": {"value": "Usually codes late at night while listening to Lofi"}}
    }
    formatted = format_memory_for_prompt(memory)
    assert "Patterns & Habits:" in formatted
    assert "Coding Habit: Usually codes late at night" in formatted
    print("✅ Formatting passed.")

def test_extraction_sensitive(api_key):
    print("Testing extraction sensitivity (calling Gemini)...")
    user_text = "I usually code around 11 PM and I love listening to Lofi music during that time."
    jarvis_text = "That's a great habit, Sahil. I'll remember that you like coding at night with Lofi."
    
    # Test should_extract_memory
    should = should_extract_memory(user_text, jarvis_text, api_key)
    print(f"Should extract: {should}")
    assert should is True
    
    # Test extract_memory
    data = extract_memory(user_text, jarvis_text, api_key)
    print(f"Extracted data: {json.dumps(data, indent=2)}")
    assert "patterns" in data or "notes" in data or "preferences" in data
    print("✅ Extraction sensitivity check (Partial) - Check output for 'patterns' field.")

if __name__ == "__main__":
    # Get API key from config if possible
    base_dir = Path(__file__).resolve().parent.parent
    config_path = base_dir / "config" / "api_keys.json"
    api_key = ""
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            api_key = json.load(f).get("gemini_api_key", "")

    try:
        test_config_loading()
        test_persistence()
        test_formatting()
        if api_key:
            test_extraction_sensitive(api_key)
        else:
            print("⚠️ API Key not found, skipping extraction test.")
        print("\nAll internal tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
