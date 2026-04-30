from __future__ import annotations
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import traceback
from pathlib import Path

from ui import JarvisUI
from core.config import (
    get_base_dir, get_config, get_api_key, 
    BASE_DIR, API_CONFIG_PATH, PROMPT_PATH,
    LIVE_MODEL, CHANNELS, SEND_SAMPLE_RATE,
    RECEIVE_SAMPLE_RATE, CHUNK_SIZE
)
# Heavy memory imports deferred to runtime
from core.utils import retry, async_retry

# Heavy imports — lazy loaded at point of use
def _lazy_sd():
    import sounddevice as sd
    return sd

def _lazy_proactive():
    from intelligence.proactive_engine import ProactiveEngine
    return ProactiveEngine

def _lazy_genai():
    from google import genai
    from google.genai import types
    return genai, types


def _get_api_key() -> str:
    return get_api_key()


def _get_config() -> dict:
    return get_config()


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )



def startup_check():
    key = _get_api_key()
    if not key or len(key.strip()) < 10:
        print("=" * 50)
        print("❌ JARVIS: API key missing hai!")
        print("   Pehle setup screen mein key enter karo.")
        print("=" * 50)
        sys.exit(1)
    
    if not PROMPT_PATH.exists():
        print(f"⚠️  WARNING: prompt.txt nahi mila: {PROMPT_PATH}")
        print("   Default prompt use hoga.")


# ── Hafıza ────────────────────────────────────────────────────────────────────
_last_memory_input = ""


def _update_memory_async(jarvis, user_text: str, jarvis_text: str) -> None:
    global _last_memory_input

    user_text   = (user_text   or "").strip()
    jarvis_text = (jarvis_text or "").strip()

    try:
        from intelligence.interaction_layer import get_interaction_layer
        get_interaction_layer().track_interaction(user_text, jarvis_text, jarvis)
    except Exception as e:
        print(f"[Interaction Layer] Error: {e}")

    if len(user_text) < 5 or user_text == _last_memory_input:
        return
    _last_memory_input = user_text

    try:
        from memory.memory_manager import should_extract_memory, extract_memory, update_memory
        api_key = _get_api_key()
        if not should_extract_memory(user_text, jarvis_text, api_key):
            return
        data = extract_memory(user_text, jarvis_text, api_key)
        if data:
            update_memory(data)
            jarvis._config_dirty = True
            print(f"[Memory] ✅ {list(data.keys())}")
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ Async update failed: {e}")

def _index_conversation_async(user_text: str, jarvis_text: str) -> None:
    """Saves every conversation turn as an embedding for semantic search."""
    if not user_text.strip() and not jarvis_text.strip():
        return
    combined = f"User: {user_text}\nJarvis: {jarvis_text}"
    try:
        from memory.semantic_memory import add_semantic_memory
        add_semantic_memory(combined)
    except Exception as e:
        print(f"[Memory] ⚠️ Indexing failed: {e}")


# ── Tool declarations ─────────────────────────────────────────────────────────
TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the Windows computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Microsoft Edge', 'Spotify')"
                },
                "action": {
                    "type": "STRING",
                    "description": "open (default) | close"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "capture_screen_context",
        "description": "Capture a screenshot and analyze the current state of the screen (active window, buttons, etc.).",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gets real-time weather information for a city.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets, lists, or deletes timed reminders using Windows Task Scheduler and local storage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING", "description": "set (default) | list | delete"},
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format (for 'set')"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h) (for 'set')"},
                "message": {"type": "STRING", "description": "Reminder message text (for 'set' or search key for 'delete')"}
            },
            "required": []
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "SYSTEM SETTINGS CONTROL: Use ONLY for Volume, Brightness, Mute, Dark Mode, WiFi, and Window State (maximize/minimize/close). "
            "Example: 'set volume to 50', 'mute', 'brighten screen'. "
            "Do NOT use for mouse movement or visual pixel tasks."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "generate_image",
        "description": (
            "Generates an AI image based on a prompt. "
            "Use for: 'make an image', 'generate wallpaper', 'create photo', etc. "
            "Automatically saves and opens the image for the user."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt_text": {"type": "STRING", "description": "Descriptive prompt for the image"}
            },
            "required": ["prompt_text"]
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls the web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, any web-based task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | press | close"},
                "url":         {"type": "STRING", "description": "URL for go_to action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up or down for scroll"},
                "key":         {"type": "STRING", "description": "Key name for press action"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_manager",
        "description": "Unified intelligent file manager. Manages files and folders: list, create, delete, move, copy, rename, read (txt/pdf/docx), write, find, search, deep_search, disk usage, organize, find_duplicates, clean_downloads, recent, info, open.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | search | deep_search | largest | disk_usage | organize_desktop | info | find_duplicates | clean_downloads | recent | open"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "query":       {"type": "STRING", "description": "Query for search/deep_search"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest/recent"},
                "days":        {"type": "INTEGER", "description": "Days for clean_downloads (default 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "cmd_control",
        "description": (
            "Runs CMD/terminal commands via natural language: disk space, processes, "
            "system info, network, find files, or anything in the command line."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task":    {"type": "STRING", "description": "Natural language description of what to do"},
                "visible": {"type": "BOOLEAN", "description": "Open visible CMD window. Default: true"},
                "command": {"type": "STRING", "description": "Optional: exact command if already known"},
            },
            "required": ["task"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": (
            "LOW-LEVEL PIXEL CONTROL: Use for mouse clicks (x,y), typing text at a specific cursor, scrolls, and finding objects on screen. "
            "Example: 'click at 500,500', 'type hello', 'scroll down'. "
            "Never use for Volume or System Settings."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "patterns — recurring habits, routines, schedule, behavior patterns | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "news_report",
        "description": "Fetches the latest real-time news headlines. Support categories like world, india, tech, sports, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "News category: world, india, technology, sports, science, health, entertainment, business"
                }
            },
            "required": []
        }
    },
    {
        "name": "daily_briefing",
        "description": "Gathers time, weather, news, and reminders for a complete daily summary.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "workflow_chain",
        "description": "Triggers a pre-defined sequence of actions for specific modes: study, coding, relax, presentation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "mode": {"type": "STRING", "description": "Mode to activate: study | coding | relax | presentation"}
            },
            "required": ["mode"]
        }
    },
    {
        "name": "browser_agent",
        "description": (
            "Advanced web automation agent. Use this for complex web tasks, "
            "logins, form filling, and intelligent data extraction. "
            "Supports headless and visible modes."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING", 
                    "description": "go_to | search | click | type | scroll | extract | fill_form | login_helper | close"
                },
                "url": {"type": "STRING", "description": "Target URL"},
                "query": {"type": "STRING", "description": "Search query"},
                "selector": {"type": "STRING", "description": "CSS selector"},
                "text": {"type": "STRING", "description": "Text to type or click"},
                "description": {"type": "STRING", "description": "Intelligent description of the element (e.g. 'login button')"},
                "press_enter": {"type": "BOOLEAN", "description": "Press Enter after typing (default: false)"},
                "direction": {"type": "STRING", "description": "Scroll direction: up | down"},
                "amount": {"type": "INTEGER", "description": "Scroll amount in pixels"},
                "headless": {"type": "BOOLEAN", "description": "Run in background (default: false for login, true for extraction)"},
                "data": {"type": "OBJECT", "description": "Data for fill_form action (description: value mappings)"},
                "timeout": {"type": "INTEGER", "description": "Timeout for login_helper in seconds"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "screen_vision",
        "description": (
            "Analyzes the screen to extract text (OCR) and detect UI elements. "
            "Use this to read error messages, detect buttons, or extract structured screen data."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "analyze (OCR + Detect) | ocr (Text only) | detect (Buttons only)"
                },
                "region": {
                    "type": "OBJECT",
                    "description": "Optional: {'top', 'left', 'width', 'height'} of the area to analyze"
                }
            },
            "required": []
        }
    },
    {
        "name": "recall_memory",
        "description": "Searches past conversations and memories semantically to find relevant context or user preferences.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "The search query (e.g. 'favourite sports' or 'previous chat about coding')"
                },
                "k": {
                    "type": "INTEGER",
                    "description": "Number of relevant memories to retrieve (default: 5)"
                }
            },
            "required": ["query"]
        }
    },

    {
        "name": "research_mode",
        "description": "Deep web research: search multiple sites, extract articles, and specialize in UPSC, Tech, or News.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "research | summarize | compare"
                },
                "query": {
                    "type": "STRING",
                    "description": "Research topic or question"
                },
                "research_mode": {
                    "type": "STRING",
                    "description": "upsc | tech | news | general"
                },
                "max_sites": {
                    "type": "INTEGER",
                    "description": "Number of sources to research (default: 3)"
                }
            },
            "required": ["action", "query"]
        }
    },
]


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command

        # Clap Activation
        config = _get_config()
        self.clap_enabled = config.get("clap_activation", False)
        if self.clap_enabled:
            try:
                from core.clap_detector import ClapDetector
                self.detector = ClapDetector()
            except Exception as e:
                print(f"[JARVIS] ClapDetector failed: {e}")
                self.detector = None
                self.clap_enabled = False
        else:
            self.detector = None

        # Wake Word Activation
        self.wake_detector = None
        self.wake_word_enabled = config.get("wake_word_activation", True)
        if self.wake_word_enabled:
            threading.Thread(target=self._load_wake_detector, daemon=True).start()

        # Session Context
        self.session_context = {
            "last_app":    None,
            "last_query":  None,
            "last_file":   None,
            "last_action": None,
            "last_tool":   None
        }

        # Multi-Step Planning
        self.active_plan = None

        # Screen Awareness
        self.screen_context = None

        # Memory Worker
        self.memory_executor = ThreadPoolExecutor(max_workers=1)
        
        # Placeholders
        self.usage_tracker = None
        self.predictive_engine = None
        self.proactive_engine = None

        # Profile & Context (Lazily Loaded)
        self._profile_manager = None
        self._personal_context = None
        self._companion_engine = None

        # Config Caching
        self._cached_config = None
        self._config_dirty = True

        # Delayed Initialization (Lazy Mode)
        self.ui.root.after(15000, self._background_lazy_init)

    @property
    def profile_manager(self):
        if self._profile_manager is None:
            from memory.profile_manager import get_manager
            self._profile_manager = get_manager()
        return self._profile_manager

    @property
    def personal_context(self):
        if self._personal_context is None:
            from intelligence.personal_context import get_personal_context
            self._personal_context = get_personal_context()
        return self._personal_context

    @property
    def companion_engine(self):
        if self._companion_engine is None:
            from emotion.companion_engine import get_companion_engine
            self._companion_engine = get_companion_engine(self)
        return self._companion_engine

    def _background_lazy_init(self):
        """Loads heavy background modules after a delay to ensure fast UI startup."""
        config = _get_config()
        
        # Predictive Engine
        def _load_predictive():
            try:
                from core.usage_tracker import UsageTracker
                from core.predictive_engine import PredictiveEngine
                log_path = BASE_DIR / "memory" / "usage_log.json"
                self.usage_tracker = UsageTracker(log_path)
                self.predictive_engine = PredictiveEngine(log_path)
                self.predictive_engine.set_mode(config.get("predictive_mode", True))
            except Exception as e:
                print(f"[JARVIS] Predictive engine failed: {e}")
        threading.Thread(target=_load_predictive, daemon=True).start()
        
        # Start Prediction Heartbeat
        self.ui.root.after(5000, self._prediction_loop)

        # Proactive Intelligence System
        def _load_proactive_sys():
            try:
                ProactiveEngine = _lazy_proactive()
                history_path = BASE_DIR / "memory" / "proactive_history.json"
                self.proactive_engine = ProactiveEngine(self, history_path)
                self.proactive_engine.start()
                self.ui.write_log("SYS: Intelligence module active.")
            except Exception as e:
                print(f"[JARVIS] Proactive system failed to load: {e}")
        
        threading.Thread(target=_load_proactive_sys, daemon=True).start()

        # Companion Engine Heartbeat (Every 15 mins)
        self.ui.root.after(900000, self._companion_heartbeat)

        # Prewarm Semantic Memory
        def _prewarm_semantic_memory():
            try:
                from memory.semantic_memory import get_semantic_memory
                get_semantic_memory()._get_model()
            except Exception as e:
                print(f"[JARVIS] Prewarm failed: {e}")
        threading.Thread(target=_prewarm_semantic_memory, daemon=True).start()

    def _companion_heartbeat(self):
        """Periodic check for proactive emotional engagement."""
        if self.companion_engine:
            msg = self.companion_engine.check_proactive()
            if msg:
                self.notify(msg, voice=True)
        
        self.ui.root.after(900000, self._companion_heartbeat)

    def notify(self, text: str, voice: bool = True):
        """Proactive notification hook."""
        self.ui.show_suggestion(text)
        if voice and not self._is_speaking and not self.ui.muted:
            self.speak(f"Sir, {text}")

    def write_log(self, text: str):
        """Proxy for UI logging — used by many tools."""
        self.ui.write_log(text)

    def _load_wake_detector(self):
        """Background thread mein Vosk model load hoga - UI freeze nahi hogi"""
        model_path = str(BASE_DIR / "models" / "vosk-model")
        try:
            from core.wake_detector import WakeWordDetector
            self.wake_detector = WakeWordDetector(model_path)
            self.ui.write_log("SYS: Wake word system ready hai.")
        except Exception as e:
            print(f"[JARVIS] ⚠️ WakeWord load failed: {e}")
            self.wake_word_enabled = False

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
            
        # Local Fast Routing Hook
        from core.local_router import route_command
        if route_command(text, self):
            return  # Completely skip Gemini AI if handled locally
            
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def _prediction_loop(self):
        """Periodic check for habit-based suggestions."""
        if self.predictive_engine and self.predictive_engine.predictive_mode:
            suggestion = self.predictive_engine.get_suggestion()
            if suggestion:
                self.ui.show_suggestion(suggestion["text"])
        
        # Check every 10 minutes (600,000 ms)
        self.ui.root.after(600000, self._prediction_loop)

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def get_user_context(self):
        """Helper to get consolidated user profile context."""
        return self.personal_context.get_context_summary()

    def _build_config(self) -> "types.LiveConnectConfig":
        if not self._config_dirty and self._cached_config:
            return self._cached_config

        from datetime import datetime
        from memory.memory_manager import load_memory, format_memory_for_prompt

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        ctx_parts = []
        if self.session_context.get("last_app"):
            ctx_parts.append(f"Last app: {self.session_context['last_app']}")
        if self.session_context.get("last_query"):
            ctx_parts.append(f"Last query: {self.session_context['last_query']}")
        if self.session_context.get("last_file"):
            ctx_parts.append(f"Last file: {self.session_context['last_file']}")
        if self.session_context.get("last_action"):
            ctx_parts.append(f"Last action: {self.session_context['last_action']}")

        session_ctx_str = ""
        if ctx_parts:
            session_ctx_str = "[SESSION CONTEXT — Use for Resolving 'it', 'that', 'usko', etc.]\n" + "\n".join(ctx_parts) + "\n\n"

        # Active Plan
        plan_str = ""
        if self.active_plan:
            steps = []
            for i, s in enumerate(self.active_plan, 1):
                status = "[DONE]" if s["done"] else "[PENDING]"
                steps.append(f"{i}. {status} {s['step']}")
            plan_str = "[ACTIVE PLAN — Stick to these steps]\n" + "\n".join(steps) + "\n\n"

        # Screen Context
        screen_ctx_str = ""
        if self.screen_context:
            screen_ctx_str = f"[SCREEN CONTEXT — What JARVIS currently 'sees']\n{self.screen_context}\n\n"

        parts = [time_ctx]
        if session_ctx_str:
            parts.append(session_ctx_str)
        if plan_str:
            parts.append(plan_str)
        if screen_ctx_str:
            parts.append(screen_ctx_str)
        if mem_str:
            parts.append(mem_str)
        
        # User Profile Context
        user_ctx = self.personal_context.get_context_summary()
        parts.append(f"[USER PERSONAL CONTEXT]\n{user_ctx}\n")

        # Emotional Context
        emotional_ctx = self.companion_engine.get_emotional_context()
        parts.append(f"{emotional_ctx}\n")

        parts.append(sys_prompt)

        _genai, _types = _lazy_genai()
        config_obj = _types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=_types.SessionResumptionConfig(),
            speech_config=_types.SpeechConfig(
                voice_config=_types.VoiceConfig(
                    prebuilt_voice_config=_types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )
        self._cached_config = config_obj
        self._config_dirty = False
        return config_obj

    async def _execute_tool(self, fc) -> "types.FunctionResponse":
        name = fc.name
        if name in ["file_controller", "file_brain"]:
            print(f"[JARVIS] ⚠️ Hallucinated tool {name} re-routed to file_manager")
            name = "file_manager"
            
        args = dict(fc.args or {})

        print(f"[JARVIS] [TOOL] {name}  {args}")
        self.ui.set_state("THINKING")

        # Update Session Context
        self.session_context["last_tool"] = name
        self._config_dirty = True
        if name == "open_app":
            self.session_context["last_app"] = args.get("app_name")
            self.session_context["last_action"] = "open_app"
        elif name == "web_search":
            self.session_context["last_query"] = args.get("query")
            self.session_context["last_action"] = "web_search"
        elif name == "file_manager":
            self.session_context["last_file"] = args.get("path")
            self.session_context["last_action"] = args.get("action")
        elif name == "browser_control":
            self.session_context["last_query"] = args.get("query") or args.get("url")
            self.session_context["last_action"] = args.get("action")
        elif name == "browser_agent":
            self.session_context["last_query"] = args.get("query") or args.get("url")
            self.session_context["last_action"] = args.get("action")

        elif name == "screen_vision":
            self.session_context["last_action"] = args.get("action", "analyze")

        # --- PREDICTIVE ENGINE LOGGING ---
        if self.usage_tracker:
            if name == "open_app":
                self.memory_executor.submit(self.usage_tracker.log_event, "app", args.get("app_name", "Unknown"))
            elif name in ["web_search", "browser_control"]:
                 self.memory_executor.submit(self.usage_tracker.log_event, "command", name)
        # --------------------------------

        # Fallback suggestions map
        FALLBACK_SUGGESTIONS = {
            "browser_control": "Sir, browser action failed. Maybe try 'computer_control' or 'cmd_control' as a fallback?",
            "open_app": "Sir, I couldn't open the app. Try using 'web_search' to find the app path or use 'cmd_control'.",
            "screen_process": "Sir, vision module failed. Is the screen content visible clearly?",
            "web_search": "Sir, search failed. I already tried fallback engines, but you might want to try 'browser_control' manually.",
            "file_manager": "Sir, file action failed. Check if the path is correct or use 'cmd_control' for direct disk access."
        }

        # ── save_memory: sessiz, hızlı, Gemini'ye bildirim yok ───────────────
        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                from memory.memory_manager import update_memory
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] [SAVE] save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        # ── manage_plan ──────────────────────────────────────────────────────
        if name == "manage_plan":
            action = args.get("action", "create")
            if action == "create":
                steps = args.get("steps", [])
                self.active_plan = [{"step": s, "done": False} for s in steps]
                self.ui.write_log(f"SYS: New Project Plan Initialised ({len(steps)} steps)")
                for i, s in enumerate(steps, 1):
                    self.ui.write_log(f"PLAN: {i}. {s}")
                result = "Plan created successfully. Sir, now start with the first step."
            elif action == "update":
                index = args.get("index", 1) - 1
                if self.active_plan and 0 <= index < len(self.active_plan):
                    self.active_plan[index]["done"] = True
                    step_text = self.active_plan[index]["step"]
                    self.ui.write_log(f"PLAN: [DONE] {step_text}")
                    result = f"Step {index+1} marked as done."
                else:
                    result = "Invalid step index or no active plan."
            elif action == "clear":
                self.active_plan = None
                self.ui.write_log("SYS: Plan cleared.")
                result = "Plan cleared."
            
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(
                id=fc.id, name=name,
                response={"result": result}
            )

        # ── capture_screen_context ───────────────────────────────────────────
        if name == "capture_screen_context":
            self.ui.set_state("THINKING")
            loop = asyncio.get_running_loop()
            
            def _blocking_capture():
                from actions.screen_processor import _capture_screenshot
                try:
                    img_bytes = _capture_screenshot()
                    _genai, _types = _lazy_genai()
                    client = _genai.Client(api_key=_get_api_key())
                    prompt = (
                        "Analyze this screenshot. Describe: 1. The active window. "
                        "2. Important buttons/text visible. 3. Their approximate coordinates (0-1000 scale, e.g. center is 500,500). "
                        "Be concise. Format as a bulleted list."
                    )
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=[
                            _types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                            prompt
                        ]
                    )
                    return response.text.strip()
                except Exception as e:
                    return f"Screen capture failed: {e}"

            try:
                self.screen_context = await loop.run_in_executor(None, _blocking_capture)
                self.ui.write_log("SYS: Screen state analyzed and updated.")
                result = f"Screen context updated: {self.screen_context}"
            except Exception as e:
                result = f"Process failed: {e}"
            
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(
                id=fc.id, name=name,
                response={"result": result}
            )

        loop   = asyncio.get_running_loop()
        
        if name == "browser_agent":
            try:
                from actions.browser_agent import browser_agent
                result = await loop.run_in_executor(None, browser_agent, args)
            except Exception as e:
                result = f"Browser Agent failed: {e}"
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(
                id=fc.id, name=name,
                response={"result": result}
            )

        if name == "generate_image":
            try:
                from actions.image_generator import generate_image
                result = await loop.run_in_executor(None, generate_image, args, self)
            except Exception as e:
                result = f"Image Generation failed: {e}"
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(
                id=fc.id, name=name,
                response={"result": result}
            )

        if name == "screen_vision":
            try:
                from actions.screen_vision import screen_vision
                result = await loop.run_in_executor(None, screen_vision, args)
            except Exception as e:
                result = f"Screen Vision failed: {e}"
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(id=fc.id, name=name, response={"result": result})

        if name == "recall_memory":
            try:
                query = args.get("query")
                k = args.get("k", 5)
                from memory.semantic_memory import search_semantic_memory
                memories = await loop.run_in_executor(None, lambda: search_semantic_memory(query, k))
                if not memories:
                    result = "No similar memories found, sir."
                else:
                    formatted = []
                    for m in memories:
                        formatted.append(f"[{m['timestamp']}] {m['text']}")
                    result = "Found similar memories:\n" + "\n".join(formatted)
            except Exception as e:
                result = f"Recall failed: {e}"
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(id=fc.id, name=name, response={"result": result})



        if name == "research_mode":
            try:
                from actions.research_mode import research_mode
                result = await loop.run_in_executor(None, research_mode, args)
            except Exception as e:
                result = f"Research Mode failed: {e}"
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return _lazy_genai()[1].FunctionResponse(id=fc.id, name=name, response={"result": result})

        result = "Done."

        # Self-healing retry loop
        attempts = 0
        max_attempts = 2
        while attempts < max_attempts:
            try:
                if name == "open_app":
                    from actions.open_app import open_app
                    r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                    result = r or f"Opened {args.get('app_name')}."
                    break # Success

                elif name == "weather_report":
                    from actions.weather_report import weather_action
                    r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                    result = r or "Weather delivered."
                    break

                elif name == "browser_control":
                    from actions.browser_control import browser_control
                    r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "file_manager":
                    from actions.file_manager import file_manager
                    r = await loop.run_in_executor(None, lambda: file_manager(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "send_message":
                    from actions.send_message import send_message
                    r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                    result = r or f"Message sent to {args.get('receiver')}."
                    break

                elif name == "reminder":
                    from actions.reminder import reminder
                    r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                    result = r or "Reminder set."
                    break

                elif name == "youtube_video":
                    from actions.youtube_video import youtube_video
                    r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "screen_process":
                    from actions.screen_processor import screen_process
                    r = await loop.run_in_executor(
                        None,
                        lambda: screen_process(parameters=args, response=None, player=self.ui, session_memory=None)
                    )
                    result = "Vision module activated. Stay completely silent — vision module will speak directly."
                    break

                elif name == "computer_settings":
                    from actions.computer_settings import computer_settings
                    r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "cmd_control":
                    from actions.cmd_control import cmd_control
                    r = await loop.run_in_executor(None, lambda: cmd_control(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "desktop_control":
                    from actions.desktop import desktop_control
                    r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "code_helper":
                    from actions.code_helper import code_helper
                    r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Done."
                    break

                elif name == "dev_agent":
                    from actions.dev_agent import dev_agent
                    r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Done."
                    break

                elif name == "agent_task":
                    from agent.task_queue import get_queue, TaskPriority
                    priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                    priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                    task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                    result   = f"Task started (ID: {task_id})."
                    break

                elif name == "web_search":
                    from actions.web_search import web_search as web_search_action
                    query = args.get("query")
                    if query:
                        self.ui.root.after(0, lambda: self.ui.open_browser_panel(query))
                    r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "computer_control":
                    from actions.computer_control import computer_control
                    r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "game_updater":
                    from actions.game_updater import game_updater
                    r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                    result = r or "Done."
                    break

                elif name == "flight_finder":
                    from actions.flight_finder import flight_finder
                    r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "news_report":
                    from actions.news import news_report
                    r = await loop.run_in_executor(None, lambda: news_report(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "daily_briefing":
                    from actions.daily_briefing import get_daily_briefing
                    r = await loop.run_in_executor(None, lambda: get_daily_briefing(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                elif name == "workflow_chain":
                    from actions.workflow_chains import workflow_chains
                    r = await loop.run_in_executor(None, lambda: workflow_chains(parameters=args, player=self.ui))
                    result = r or "Done."
                    break

                else:
                    result = f"Unknown tool: {name}"
                    break

            except Exception as e:
                attempts += 1
                if attempts < max_attempts:
                    print(f"[Self-Healing] [WARN] Attempt {attempts} failed for {name}: {e}. Retrying...")
                    
                    if name == "file_manager" and "path" in args:
                        clean_path = args["path"].strip().strip("'\"").replace("\\\\", "\\")
                        print(f"[Self-Healing] Cleaning path: '{args['path']}' -> '{clean_path}'")
                        args["path"] = clean_path
                        
                    await asyncio.sleep(0.2)
                    continue
                
                # Final failure
                suggestion = FALLBACK_SUGGESTIONS.get(name, "Sir, something went wrong. Try another approach?")
                error_str = str(e)
                if isinstance(e, FileNotFoundError) or "No such file" in error_str:
                    err_msg = f"File or directory not found: {args.get('path', '')}"
                elif isinstance(e, PermissionError) or "Access is denied" in error_str:
                    err_msg = f"Permission denied for path: {args.get('path', '')}"
                elif isinstance(e, OSError) and ("Invalid argument" in error_str or "syntax" in error_str.lower()):
                    err_msg = f"Invalid file path syntax: {args.get('path', '')}"
                elif isinstance(e, ValueError):
                    err_msg = error_str
                else:
                    err_msg = error_str
                    
                result = f"Error: {err_msg}\n[SUGGESTION]: {suggestion}"
                traceback.print_exc()
                self.speak_error(name, e)
                break

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")

        # ── Result: tek cümle söyle, dur ──────────────────────────────────────
        return _lazy_genai()[1].FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            if getattr(self, "tool_call_pending", False):
                continue  # Stop sending audio inputs while processing function responses to prevent 1008 policy violations
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking

            # Clap Detection (works even when muted)
            if self.clap_enabled and self.detector and not jarvis_speaking:
                if self.detector.is_clap(indata):
                    print("[JARVIS] 👏 Clap detected!")
                    if self.ui.muted:
                        # Activate/Unmute
                        self.ui.root.after(0, self.ui._toggle_mute)
                    else:
                        # Feedback if already active
                        self.ui.write_log("SYS: Clap detected (Already active).")

            # Wake Word Detection (works even when muted)
            if self.wake_word_enabled and self.wake_detector and not jarvis_speaking:
                if self.wake_detector.check(indata):
                    print("[JARVIS] 🎙️ Wake word detected!")
                    if self.ui.muted:
                        # Activate/Unmute
                        self.ui.root.after(0, self.ui._toggle_mute)
                    else:
                        self.ui.write_log("SYS: Wake word detected (Already active).")

            if not jarvis_speaking and not self.ui.muted:
                data = indata.tobytes()
                loop.call_soon_threadsafe(
                    self.out_queue.put_nowait,
                    {"data": data, "mime_type": "audio/pcm"}
                )

        while True:
            try:
                with _lazy_sd().InputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    callback=callback,
                ):
                    print("[JARVIS] 🎤 Mic stream open")
                    while True:
                        await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[JARVIS] ❌ Mic Error: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            txt = sc.output_transcription.text.strip()
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = sc.input_transcription.text.strip()
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            self.set_speaking(False)

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            out_buf = []

                            if full_in:
                                self.memory_executor.submit(_update_memory_async, self, full_in, full_out)
                                self.memory_executor.submit(_index_conversation_async, full_in, full_out)
                                
                                # Emotional Awareness Support
                                caring_msg = self.companion_engine.process_interaction(full_in)
                                if caring_msg:
                                    self.ui.root.after(2000, lambda m=caring_msg: self.notify(m, voice=True))

                    if response.tool_call:
                        self.tool_call_pending = True
                        try:
                            fn_responses = []
                            for fc in response.tool_call.function_calls:
                                print(f"[JARVIS] 📞 {fc.name}")
                                fr = await self._execute_tool(fc)
                                fn_responses.append(fr)
                            await self.session.send_tool_response(
                                function_responses=fn_responses
                            )
                        finally:
                            self.tool_call_pending = False
                        # ── Boş turn YOK — bu "Anladım." sorununu yaratıyordu ──

        except Exception as e:
            print(f"[JARVIS] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")
        loop = asyncio.get_event_loop()

        # Sürekli açık output stream — PyAudio'daki stream.write() davranışıyla aynı
        stream = _lazy_sd().RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
                # Reset speaking state if no more chunks are immediately pending
                if self.audio_in_queue.empty():
                    self.set_speaking(False)
        except Exception as e:
            print(f"[JARVIS] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        _genai, _types = _lazy_genai()
        client = _genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        first_run   = True
        retry_delay = 2 # Initial backoff seconds

        while True:
            try:
                print(f"[JARVIS] 🔌 Connecting (Retry delay: {retry_delay}s)...")
                self.ui.set_state("THINKING")
                self.ui.write_log("SYS: Connecting to Gemini...")
                
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_running_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=100)

                    print("[JARVIS] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online. Ready to help.")
                    
                    # Connection established, reset backoff
                    retry_delay = 2

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

                    # Startup Briefing Trigger (Only on first run)
                    if first_run:
                        first_run = False
                        await asyncio.sleep(2) # Wait for audio setup
                        await session.send_client_content(
                            turns={"parts": [{"text": "System call: Perform 'daily_briefing' for Sahil now."}]},
                            turn_complete=True
                        )
                    
                    # Ensure the loop within TaskGroup doesn't exit immediately unless exception occurs
                    while True:
                        await asyncio.sleep(1)

            except Exception as e:
                print(f"[JARVIS] ⚠️ Connection error: {e}")
                self.ui.write_log(f"SYS: Connection lost ({e}). Reconnecting in {retry_delay}s...")
                self.ui.set_state("INITIALISING")
                self.session = None
                self.set_speaking(False)
                
                await asyncio.sleep(retry_delay)
                # Exponential backoff: capped at 30s
                retry_delay = min(retry_delay * 2, 30)


def main():
    startup_check()
    ui = JarvisUI("face.png")

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
