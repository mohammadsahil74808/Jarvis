import os
import sys
import json
from pathlib import Path
from functools import lru_cache

def get_base_dir() -> Path:
    """Returns the base directory of the JARVIS project."""
    if getattr(sys, "frozen", False):
        # If running as a compiled executable
        return Path(sys.executable).parent
    # Standard script execution
    return Path(__file__).resolve().parent.parent

# --- Project-wide Constants ---
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

BASE_DIR        = get_base_dir()
CONFIG_DIR      = BASE_DIR / "config"
API_CONFIG_PATH = CONFIG_DIR / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"

@lru_cache()
def get_config() -> dict:
    """Reads and caches the API configuration from api_keys.json."""
    try:
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Config] ⚠️ Failed to load config: {e}")
    return {}

def get_api_key() -> str:
    """Helper to retrieve the Gemini API key."""
    return get_config().get("gemini_api_key", "")

def get_groq_api_key() -> str:
    """Helper to retrieve the Groq API key."""
    return get_config().get("groq_api_key", "")

def get_together_api_key() -> str:
    """Helper to retrieve the Together AI API key."""
    return get_config().get("together_api_key", "")

def get_huggingface_api_key() -> str:
    """Helper to retrieve the Hugging Face API key."""
    return get_config().get("huggingface_api_key", "")
