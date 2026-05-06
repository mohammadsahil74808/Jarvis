# agent/tool_definitions.py

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
        "name": "website_builder",
        "description": "Build complete production-ready websites with AI. Creates portfolios, SaaS sites, e-commerce, dashboards, blogs, 3D sites, landing pages. Auto-setup, install deps, open browser preview. Use when user wants to create/build/make a website.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {
                    "type": "STRING",
                    "description": "Full description of what website to build"
                },
                "deploy_to": {
                    "type": "STRING",
                    "enum": ["none", "vercel", "netlify", "docker"],
                    "description": "Where to deploy after building (default: none)"
                },
                "use_template": {
                    "type": "STRING",
                    "description": "Template name to use: dev_portfolio, saas_landing, creative_agency, minimal_blog, ai_tool, ecommerce, 3d_portfolio, restaurant"
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "app_builder",
        "description": "Build complete Flutter mobile apps with AI. Creates social, chat, ecommerce, fitness, finance, AI chat, music, dashboard apps. Full project with screens, auth, theme, navigation. Use when user wants to build a mobile app.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {
                    "type": "STRING",
                    "description": "Full description of the mobile app to build"
                },
                "build_apk": {
                    "type": "BOOLEAN",
                    "description": "Build debug APK after project creation"
                },
                "use_template": {
                    "type": "STRING",
                    "description": "Template: social_app | chat_app | ecommerce_app | fitness_app | ai_chat_app | todo_app | music_app | dashboard_app"
                }
            },
            "required": ["prompt"]
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
    {
        "name": "shutdown_system",
        "description": "Closes the JARVIS application safely. Call this ONLY when the user explicitly says goodbye, wants to close the program, or tells you to stop running.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "confirm": {"type": "BOOLEAN", "description": "Set to true to confirm shutdown"}
            },
            "required": ["confirm"]
        }
    },
]
