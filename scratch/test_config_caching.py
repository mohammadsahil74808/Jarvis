import sys
import os
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from core.config import get_config, invalidate_config_cache, API_CONFIG_PATH
from memory.config_manager import save_api_keys

def test_config_caching():
    print("Starting Config Caching Test...")
    
    # 1. Ensure config file exists with dummy data
    API_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    initial_data = {"gemini_api_key": "initial_key_12345"}
    API_CONFIG_PATH.write_text(json.dumps(initial_data), encoding="utf-8")
    
    # 2. Load config (should cache)
    config1 = get_config()
    print(f"Loaded config: {config1}")
    
    # 3. Modify file manually
    API_CONFIG_PATH.write_text(json.dumps({"gemini_api_key": "modified_key_67890"}), encoding="utf-8")
    
    # 4. Load config again (should still be initial_key_12345 because of cache)
    config2 = get_config()
    print(f"Loaded config again (cached): {config2}")
    
    if config2["gemini_api_key"] == "initial_key_12345":
        print("SUCCESS: Cache is working.")
    else:
        print("FAILURE: Cache is not working!")
        return

    # 5. Save via config_manager (should invalidate)
    print("Saving new key via config_manager...")
    save_api_keys("new_key_from_manager")
    
    # 6. Load config again (should be new_key_from_manager)
    config3 = get_config()
    print(f"Loaded config after save: {config3}")
    
    if config3["gemini_api_key"] == "new_key_from_manager":
        print("SUCCESS: Invalidation is working.")
    else:
        print("FAILURE: Invalidation failed!")
        return

    print("All tests passed!")

if __name__ == "__main__":
    # Backup existing config
    backup = None
    if API_CONFIG_PATH.exists():
        backup = API_CONFIG_PATH.read_text(encoding="utf-8")
    
    try:
        test_config_caching()
    finally:
        # Restore backup
        if backup:
            API_CONFIG_PATH.write_text(backup, encoding="utf-8")
        else:
            if API_CONFIG_PATH.exists(): API_CONFIG_PATH.unlink()
