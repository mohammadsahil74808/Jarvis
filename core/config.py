import os
import sys
import json
from pathlib import Path
from google import genai

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

_config_cache = None

def get_config() -> dict:
    """Reads and caches the API configuration from api_keys.json."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    try:
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
                return _config_cache
    except Exception as e:
        print(f"[Config] [WARNING] Failed to load config: {e}")
    
    return {}

def invalidate_config_cache():
    """Clears the internal config cache and reset the Gemini client."""
    global _config_cache, _client
    _config_cache = None
    _client = None

_client = None

def get_gemini_client():
    """Returns a singleton instance of the Gemini Client."""
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=get_api_key()
        )
    return _client

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

def get_desktop_path() -> Path:
    """Returns a reliable path to the user's Desktop, handling OneDrive redirection."""
    # 1. Try winshell (Best for Windows)
    try:
        import winshell
        return Path(winshell.desktop())
    except Exception:
        pass

    # 2. Use reliable Windows API via ctypes (Standard on Windows)
    try:
        import ctypes.wintypes
        CSIDL_DESKTOP = 0x0000 
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetSpecialFolderPathW(None, buf, CSIDL_DESKTOP, False)
        if buf.value:
            return Path(buf.value)
    except Exception:
        pass

    # 3. Fallback to environment variable or Path.home()
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        path = Path(user_profile) / "Desktop"
        if path.exists(): return path

    return Path.home() / "Desktop"

def get_downloads_path() -> Path:
    """Returns a reliable path to the user's Downloads folder."""
    one_drive = Path.home() / "OneDrive" / "Downloads"
    if one_drive.exists(): return one_drive
    return Path.home() / "Downloads"

def get_documents_path() -> Path:
    """Returns a reliable path to the user's Documents folder."""
    one_drive = Path.home() / "OneDrive" / "Documents"
    if one_drive.exists(): return one_drive
    return Path.home() / "Documents"
