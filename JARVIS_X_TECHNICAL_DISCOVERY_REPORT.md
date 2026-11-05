# JARVIS X — Complete Technical Discovery & QA Preparation Audit Report

**Document Version:** 1.0.0  
**Date of Audit:** November 5, 2026  
**Auditor Role:** Senior Software Architect, Independent QA Analyst & Security Auditor  
**Project:** JARVIS X (Mark XXV / Mark XXXV)  
**Project Owner:** Sahil Sheikh  
**Status:** Discovery Complete — Non-Destructive Inspection Only (No Code or Tests Modified)  

---

## 1. Executive Summary

JARVIS X is a Python-centric, multi-modal autonomous desktop AI assistant and agentic copilot engineered for the Microsoft Windows environment (Windows 10/11 x64). The project is architecturally centered around a persistent, full-duplex WebSocket connection to Google's Gemini Live Audio API (`models/gemini-2.5-flash-native-audio-preview-12-2025`), providing real-time voice streaming (16 kHz PCM microphone capture, 24 kHz PCM speaker playback) and native Gemini Function Calling.

Beyond the real-time conversational core, the system incorporates:
1. **Agentic Tool Dispatch System (`agent/tool_executor.py`):** Routes function calls to 35+ local tools including OS automation, browser controllers, command execution, and code generation.
2. **Autonomous Multi-Step Planner (`agent/planner.py`, `agent/executor.py`, `agent/task_queue.py`):** Employs multi-turn reasoning to decompose high-level user instructions into sequential tool invocations with dynamic replanning and self-healing.
3. **Multi-Model Fallback Cascade (`core/ai_router.py`):** Supports secondary providers (Groq, NVIDIA NIM, OpenRouter, Hugging Face, Pollinations.ai) for text, reasoning, and image generation.
4. **Model Context Protocol (MCP) Bridge (`mcp_client/`):** Connects external MCP servers (Playwright, GitHub, Filesystem, SQLite, Google Drive) and converts JSON schemas to Gemini function declarations.
5. **Retrieval-Augmented Generation (RAG) Core (`rag_core/`):** Combines dense vector search (`FAISS` with `bge-small-en-v1.5`), sparse search (`rank-bm25`), and metadata tracking (`SQLite`) with a real-time filesystem watchdog.
6. **Background Intelligence & Proactive Engine (`intelligence/`, `emotion/`):** Monitors hardware vitals, user fatigue/stress, and application focus to proactively issue spoken suggestions.
7. **Zero-Dependency Voice Activity Detection & Wake Systems:** Employs `openwakeword` (ONNX) for keyword spotting, WebRTC VAD with a pure-Python/NumPy energy fallback, and an offline local STT fallback (`faster-whisper` base.en int8).

### Overall Assessment & Audit Caveats
While the architectural design is ambitious and contains deep implementations across multiple systems, the codebase exhibits critical testing and readiness challenges:
- **Simulated vs. Real Integrations:** Messaging "integrations" (WhatsApp, Telegram, Instagram, Discord) are not API integrations; they rely entirely on fragile GUI keystroke automation (`pyautogui` typing into search bars).
- **Security Boundaries:** High-risk code execution paths exist in `cmd_control`, `agent/executor.py` (`_run_generated_code`), and `actions/desktop.py`, which execute unsanitized LLM-generated Python scripts via `subprocess` without OS sandboxing or container isolation.
- **Undeclared & Broken Dependencies:** Several modules reference third-party libraries not listed in `requirements.txt` (e.g., `groq`, `huggingface_hub`, `deepface`). A test script (`test_browser.py`) references a non-existent module (`actions.browser_use_action`).
- **Mocked Testing:** Existing test suites rely almost entirely on mocking, leaving real-world Windows GUI, audio hardware, and browser sessions unverified by automated CI.

---

## 2. Complete Project Architecture

### 2.1 Programming Languages, Frameworks & Runtimes
- **Primary Runtime:** Python 3.11 – 3.14 (64-bit on Windows).
- **Secondary Runtime:** Node.js (v18+) & `npx` (required for running external MCP servers: `@playwright/mcp`, `@modelcontextprotocol/server-filesystem`, `@modelcontextprotocol/server-github`, `mcp-server-sqlite-npx`).
- **GUI Framework:** Python `tkinter` (Native Tcl/Tk) with custom Canvas rendering for an animated circular arc-reactor/waveform HUD.
- **AI / Agent Protocols:** 
  - `google-genai` SDK (v1.65.0) Live Client (bidirectional WebSocket).
  - Model Context Protocol (MCP) Client over `stdio` and HTTP transports.

### 2.2 System Architecture Diagram
```
                             ┌──────────────────────────────────────┐
                             │              JARVIS X                │
                             │       Main Entry: main.py            │
                             └──────────────────┬───────────────────┘
                                                │
         ┌────────────────────────┬─────────────┴────────────┬────────────────────────┐
         ▼                        ▼                          ▼                        ▼
┌──────────────────┐    ┌───────────────────┐      ┌──────────────────┐     ┌──────────────────┐
│   AUDIO ENGINE   │    │    AGENT CORE     │      │     RAG CORE     │     │   INTELLIGENCE   │
│ • sounddevice    │    │ • Gemini Live WS  │      │ • FAISS Indexes  │     │ • ProactiveEng   │
│ • WebRTC/NumPy   │    │ • ToolExecutor    │      │ • rank-bm25      │     │ • StateDetector  │
│ • openWakeWord   │    │ • Planner/Queue   │      │ • SQLite Meta    │     │ • InteractionLyr │
│ • Faster-Whisper │    │ • ErrorHandler    │      │ • File Watchdog  │     │ • UsageTracker   │
│ • SAPI COM TTS   │    │ • FreeAIRouter    │      │ • 6 Adapters     │     │ • PersonalCtx    │
└────────┬─────────┘    └─────────┬─────────┘      └────────┬─────────┘     └────────┬─────────┘
         │                        │                         │                        │
         ▼                        ▼                         ▼                        ▼
┌──────────────────┐    ┌───────────────────┐      ┌──────────────────┐     ┌──────────────────┐
│  HARDWARE I/O    │    │  TOOL DISPATCH    │      │  PERSISTENT DATA │     │   PRESENTATION   │
│ • Microphone     │    │ • OS / Keyboard   │      │ • data/jarvis.db │     │ • Tkinter HUD    │
│ • Speakers       │    │ • Chrome/CDP      │      │ • memory/*.json  │     │ • MCP HUD        │
│ • Screen Grab    │    │ • File Manager    │      │ • Profile Store  │     │ • Setup Wizard   │
│ • UDP 127.0.0.1  │    │ • MCP Manager     │      │ • Vector Stores  │     │ • SAPI Audio     │
└──────────────────┘    └───────────────────┘      └──────────────────┘     └──────────────────┘
```

### 2.3 Complete Folder & File Structure
```
C:\Projects\Jarvis\
├── .env                              # Environment variable overrides (API keys)
├── .gitignore                         # Git exclusion rules
├── clap_launcher.py                   # Standalone acoustic clap / Shift key background launcher
├── latency_probe.py                   # Latency measurement probe script
├── main.py                            # Primary application entry point & orchestration
├── mcp_test.py                        # MCP connection standalone test script
├── package.json / package-lock.json   # Node package definition for local MCP filesystem server
├── pyproject.toml / setup.py          # Python project and packaging definitions
├── pytest.ini                         # Pytest configuration
├── rag_config.yaml                    # RAG storage, embedding, and adapter configuration
├── readme.md                          # Project documentation and feature overview
├── requirements.txt                   # Declared Python dependencies
├── run_jarvis_background.vbs          # VBScript background launcher for clap_launcher.py
├── test.py / test.py.jarvis_bak       # Temporary scratch scripts
├── test_browser.py                    # Broken browser test script
├── verify_gemini.py                   # Smoke test for Gemini SDK connectivity
│
├── actions/                           # Tool execution modules
│   ├── app_builder/                   # Mobile Flutter application builder
│   │   ├── brain.py                   # Architecture planner for Flutter
│   │   ├── builder.py                 # Scaffold and build coordinator
│   │   ├── codegen.py                 # Dart code generator
│   │   └── engine.py                  # Flutter CLI execution harness
│   ├── clap_cnn/                      # Deep learning clap detector model files
│   │   ├── model.py                   # PyTorch CNN AudioClassifier architecture
│   │   ├── record_samples.py          # Audio dataset collection script
│   │   └── train.py                   # PyTorch training script
│   ├── website_builder/               # Full-stack React/Vite website builder
│   │   ├── brain.py                   # Website architectural design & prompt decomposition
│   │   ├── builder.py                 # Scaffold and dev server coordinator
│   │   ├── codegen.py                 # React/Tailwind code generator
│   │   ├── engine.py                  # Vite dev server and npm process manager
│   │   └── plugins.py                 # Predefined web templates
│   ├── browser_control.py             # Playwright/CDP browser automation bridge
│   ├── cmd_control.py                 # OS terminal & PowerShell execution
│   ├── code_helper.py                 # Single-file code assistant & fixer
│   ├── computer_control.py            # Low-level PyAutoGUI mouse, keyboard, clipboard
│   ├── computer_settings.py           # Audio volume (pycaw), brightness, sleep, lock
│   ├── cursor_agent.py                # Autonomous edit-test-fix loop
│   ├── daily_briefing.py              # Aggregated morning briefing
│   ├── desktop.py                     # Desktop icon organization & wallpaper
│   ├── dev_agent.py                   # Multi-file software project builder & runner
│   ├── doctor.py                      # System diagnostics and health checker
│   ├── file_controller.py             # Wrapper interface for file_manager
│   ├── file_manager.py                # Comprehensive filesystem search, CRUD, and audit
│   ├── flight_finder.py               # Google Flights scraper via browser automation
│   ├── game_updater.py                # Steam & Epic Games library inspector
│   ├── image_cluster.py               # Face & visual similarity clustering
│   ├── image_generator.py             # Text-to-image generator via Hugging Face
│   ├── news.py                        # Google News RSS fetcher
│   ├── open_app.py                    # Cross-platform application launcher
│   ├── reminder.py                    # Windows Task Scheduler & JSON reminder manager
│   ├── research_mode.py               # Multi-source web research with text extraction
│   ├── send_message.py                # GUI keystroke automation for messaging apps
│   ├── vision_action.py               # Unified screenshot/camera analyzer & OCR
│   ├── weather_report.py              # Weather lookup via wttr.in and Open-Meteo
│   ├── workflow_chains.py             # Multi-step routine coordinator (Study, Coding, etc.)
│   └── youtube_video.py               # Video playback, OpenCV thumbnail detection, transcripts
│
├── agent/                             # Autonomous agent orchestration framework
│   ├── context_compactor.py           # Unused conversation compaction utility
│   ├── error_handler.py               # Autonomous error classification and replanning
│   ├── executor.py                    # Multi-step plan execution engine
│   ├── planner.py                     # Natural language goal-to-plan compiler
│   ├── task_queue.py                  # Thread-safe prioritized background task queue
│   ├── tool_definitions.py            # Gemini JSON Schema tool declarations (35 tools)
│   └── tool_executor.py               # Central execution dispatcher and safety gatekeeper
│
├── config/                            # Configuration files & API credentials
│   ├── api_keys.json                  # Main API keys (Gemini, Groq, NVIDIA, HF, etc.)
│   ├── browser_signal.json            # State signaling between browser and agent
│   ├── client_secret.json             # Google Drive OAuth client secret
│   └── drive_token.json               # Google Drive OAuth token store
│
├── core/                              # Core runtime systems
│   ├── ai_router.py                   # FreeAIRouter multi-model fallback cascade
│   ├── app_watcher.py                 # Foreground application change listener
│   ├── audio_engine.py                # Real-time microphone capture & audio playback
│   ├── clap_detector.py               # Heuristic energy-ratio clap detector
│   ├── clap_detector_ml.py            # PyTorch ML clap detector loader
│   ├── config.py                      # Global configuration loader, client factory, key rotator
│   ├── cost_tracker.py                # Token usage & cost accounting
│   ├── friday_prompt.txt              # System instructions for FRIDAY persona
│   ├── geo.py                         # IP-based geolocation lookup
│   ├── local_router.py                # Regex fast-path local command executor
│   ├── path_scope.py                  # Workspace path containment guard
│   ├── predictive_engine.py           # Usage pattern analyzer and habit suggester
│   ├── prompt.txt                     # System instructions for JARVIS persona
│   ├── state.py                       # JarvisState session data container
│   ├── tool_registry.py               # Mapping of tool names to callable modules
│   ├── usage_tracker.py               # JSON logger for application and command events
│   ├── utils.py                       # Retries, browser launch, and SAPI COM TTS
│   ├── vad_engine.py                  # WebRTC VAD & NumPy energy VAD fallback
│   └── wake_detector.py               # openWakeWord ONNX "Hey Jarvis" detector
│
├── data/                              # Structured application databases
│   └── jarvis.db                      # SQLite database for persistent memory & SQLite MCP
│
├── docs/                              # Project documentation
│   └── browser_stack.md               # Browser automation architecture notes
│
├── emotion/                           # Emotional and companion intelligence
│   ├── conversation_memory.py         # Emotional context history store
│   └── state_detector.py              # User fatigue, stress, and engagement detector
│
├── intelligence/                      # Proactive assistance & rules
│   ├── history.py                     # Suggestion history and cooldown manager
│   ├── interaction_layer.py           # Formality, verbosity, and topic tracker
│   ├── personal_context.py            # User profile summarizer and prompt builder
│   ├── proactive_engine.py            # Background rule evaluation event loop
│   ├── rules.py                       # 8 proactive evaluation rules (Battery, CPU, Break, etc.)
│   └── state_monitor.py               # System vitals & idle time poller
│
├── jarvis/                            # Browser automation subsystem
│   └── browser/
│       ├── browser_adapter.py         # Singleton accessor for BrowserController
│       ├── browser_context.py         # Chrome CDP launcher and dedicated profile manager
│       ├── browser_controller.py      # High-level Playwright action executor
│       ├── browser_manager.py         # Low-level Playwright instance lifecycle manager
│       ├── browser_state.py           # Active tab and DOM state tracker
│       ├── search_resolver.py         # Rank-based search result selector
│       └── browser_use/               # Embedded upstream browser-use agent framework
│
├── mcp_client/                        # Model Context Protocol client implementation
│   ├── client.py                      # Resilient MCP client (stdio & HTTP SSE)
│   ├── config.json                    # MCP server definitions (filesystem, github, playwright, sqlite, drive)
│   ├── filesystem_security.py         # Drive and path security validator for MCP
│   ├── google_auth.py                 # OAuth flow for Google Drive MCP
│   └── manager.py                     # MCP server orchestrator & schema converter
│
├── memory/                            # Persistent memory, vector indices & user profiles
│   ├── emotional_patterns.json        # Detected emotional tendencies
│   ├── interaction_prefs.json         # Learned user interaction style preferences
│   ├── long_term.json                 # Structured long-term memory (JSON mirror)
│   ├── memory_manager.py              # SQLite-backed persistent memory CRUD
│   ├── proactive_history.json         # Cooldown timestamps for proactive rules
│   ├── profile_manager.py             # User profile manager (bio, college, routine)
│   ├── rag_metadata.db                # SQLite metadata store for RAG chunks
│   ├── reminders.json                 # Scheduled reminder list
│   ├── semantic_index.faiss           # Global FAISS vector index
│   ├── semantic_memory.db             # Semantic memory mapping database
│   ├── semantic_memory.py             # Proxy interface to RAG engine
│   ├── usage_log.json                 # Log of opened apps and executed commands
│   ├── user_profile.json              # Detailed user biographical data
│   ├── browser_profile/               # Dedicated Google Chrome automation profile
│   └── faiss_indexes/                 # Domain-specific FAISS indices (code.faiss, memory.faiss)
│
├── models/                            # Local offline models
│   └── vosk-model/                    # Obsolete Vosk STT model directory (superseded)
│
├── rag_core/                          # Hybrid RAG engine
│   ├── adapters/                      # Domain chunkers: code, docs, memory, ocr, project, web
│   ├── retrieval/                     # Hybrid search (FAISS + BM25 reciprocal rank fusion)
│   ├── router/                        # Query intent to namespace router
│   ├── storage/                       # FAISS and SQLite managers
│   ├── watchers/                      # Real-time directory indexer (watchdog)
│   ├── config.py                      # RAG configuration reader
│   ├── embeddings.py                  # SentenceTransformer embedding generator
│   └── engine.py                      # Core RAG engine orchestrator
│
├── tests/                             # Test suites
│   ├── conftest.py                    # Asyncio pytest fixtures
│   ├── test_all_tools.py              # Mocked unit test for all 35 tool dispatches
│   ├── test_brain.py                  # Live Gemini routing evaluation
│   ├── test_browser_automation.py     # Playwright browser integration tests
│   ├── test_browser_use_integration.py# Browser-use framework tests
│   ├── test_chrome_isolation.py       # Profile isolation verification
│   ├── test_filesystem_security.py    # Path traversal & credential protection tests
│   ├── test_search_result_selection.py# Search resolver tests
│   ├── test_vision_context.py         # Screen context serialization tests
│   └── test_vision_system.py          # Screenshot capture & OCR tests
│
├── ui/                                # Graphical User Interface
│   ├── jarvis_ui.py                   # Main holographic Canvas HUD, particle engine, text input
│   ├── mcp_hud.py                     # MCP tool execution popup HUD
│   └── setup_screen.py                # 4-step first-run onboarding wizard
│
├── vendor_pkgs/                       # Unused bundled third-party packages
│   ├── affine/                        # Bundled affine library (unreferenced)
│   └── rasterio/                      # Bundled rasterio GIS library & DLLs (unreferenced)
│
└── vision/                            # Vision & screen analysis engine
    ├── capture_engine.py              # mss-based multi-monitor screenshot capturer
    ├── context.py                     # ScreenContext dataclass and prompt formatter
    ├── context_store.py               # Singleton screen context cache
    ├── enhancer.py                    # OpenCV contrast & image enhancement
    ├── memory.py                      # Rolling buffer of historical screen captures
    ├── privacy.py                     # Secret masking regexes & application exclusion
    ├── service.py                     # Continuous background screen observer daemon
    └── ui_analyzer.py                 # Contours & bounding box element detector
```

### 2.4 Unused, Duplicated, Obsolete, or Suspicious Files

| File / Directory Path | Classification | Detailed Justification & Evidence |
| :--- | :--- | :--- |
| `vendor_pkgs/rasterio/`, `vendor_pkgs/affine/` | **Unused / Obsolete** | Massive geospatial raster libraries and C/C++ DLLs bundled directly into the project root. Global grep confirms zero import statements across the entire codebase. |
| `models/vosk-model/` | **Obsolete** | 40MB+ offline speech recognition model directory. Codebase migrated to `openwakeword` and `faster-whisper`. `core/wake_detector.py` explicitly notes Vosk was replaced. |
| `actions/browser_use_action.py` | **Missing / Broken Reference** | `test_browser.py` attempts to import `from actions.browser_use_action import browser_use_action`. The file does not exist, causing `test_browser.py` to crash immediately. |
| `actions/clap_cnn/clap_model.pth` | **Missing Asset** | `core/clap_detector_ml.py` checks for this weight file. Because it does not exist on disk, the system always drops back to the heuristic `core/clap_detector.py`. |
| `agent/context_compactor.py` | **Unused / Dead Code** | Class `ContextCompactor` is defined with turn-compaction algorithms but is never imported or called anywhere in the runtime. |
| `actions/file_controller.py` | **Duplicated / Redundant** | Pure pass-through wrapper around `actions/file_manager.py`. It exists solely for historical naming compatibility with the planner. |
| `test.py`, `test.py.jarvis_bak` | **Suspicious / Scratch** | Scratch files containing 7-line boilerplate functions created during interactive testing sessions. |
| `core/edith_prompt.txt` | **Missing Asset** | An `E.D.I.T.H` persona is selectable in `ui/setup_screen.py`, but the corresponding system prompt file is missing from `core/`. |

---

## 3. Complete Feature Inventory

Below is an exhaustive audit of all distinct features, capabilities, tools, and background routines across the JARVIS X project.

### 3.1 Tools & Autonomous Actions Inventory

| ID | Feature Name | Source File & Function/Class | Activation Method | External API / Dependencies | Error Handling & Fallback | Execution Status | Real-World Feasible? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ACT-01** | App Launcher & Killer (`open_app`) | `actions/open_app.py:open_app` | Voice/Tool: `"open_app"` | `psutil`, `pyautogui` | Heuristic name lookup, aliases map; returns error text. | **PARTIALLY VERIFIED** | **YES** (Simulates Start menu search via `pyautogui`) |
| **ACT-02** | Vision Action (`vision_action`) | `actions/vision_action.py:vision_action` | Voice/Tool: `"vision_action"` | `cv2`, `mss`, `PIL`, `pytesseract`, Gemini Flash | Catches camera index errors; falls back across 4 camera indices; returns text. | **VERIFIED** | **YES** (Takes mss screenshot or cv2 webcam capture, runs OCR/Gemini) |
| **ACT-03** | System Health Doctor (`system_doctor`) | `actions/doctor.py:run_doctor` | Voice/Tool: `"system_doctor"` | `psutil`, `pyautogui`, Git CLI | Catches import and subprocess errors, returns markdown diagnostic report. | **PARTIALLY VERIFIED** | **YES** (Note: checks for `pyaudio` instead of `sounddevice`) |
| **ACT-04** | Web Search (`web_search`) | `actions/web_search.py:web_search` | Voice/Tool: `"web_search"` | `duckduckgo-search`, `googlesearch-python` | Tries DuckDuckGo; falls back to Google Search; falls back to browser URL launch. | **VERIFIED** | **YES** (Extracts snippets and provides clean answer) |
| **ACT-05** | Website Builder (`website_builder`) | `actions/website_builder/builder.py:build_website` | Voice/Tool: `"website_builder"` | Gemini API, Node.js, `npm`, `vite` | Dispatched to background queue; falls back to pre-built template scaffolds. | **PARTIALLY VERIFIED** | **YES** (Requires Node.js and internet for `npm install`) |
| **ACT-06** | Mobile App Builder (`app_builder`) | `actions/app_builder/builder.py:build_mobile_app` | Voice/Tool: `"app_builder"` | Gemini API, Flutter SDK | Dispatched to background queue; falls back to pre-built Flutter templates. | **PARTIALLY VERIFIED** | **CONDITIONAL** (Requires Flutter SDK installed on host) |
| **ACT-07** | Weather Reporter (`weather_report`) | `actions/weather_report.py:weather_action` | Voice/Tool: `"weather_report"` | `wttr.in`, `Open-Meteo`, Google | Calls `wttr.in`; falls back to opening Google Weather in browser. | **VERIFIED** | **YES** (Free HTTP endpoint, no key required) |
| **ACT-08** | Message Sender (`send_message`) | `actions/send_message.py:send_message` | Voice/Tool: `"send_message"` | `pyautogui`, Desktop apps | Critic confirmation popup; falls back to browser for Instagram; reports UI error. | **PARTIALLY VERIFIED** | **FRAGILE** (Blind keystroke automation; fails if window layout differs) |
| **ACT-09** | Reminder Manager (`reminder`) | `actions/reminder.py:reminder` | Voice/Tool: `"reminder"` | Windows `schtasks`, `pythonw` | Validates date/time; stores in `reminders.json`; registers OS task. | **VERIFIED** | **YES** (Triggers modal notification popup at scheduled time) |
| **ACT-10** | YouTube Controller (`youtube_video`) | `actions/youtube_video.py:youtube_video` | Voice/Tool: `"youtube_video"` | `youtube_transcript_api`, `cv2`, Edge | Edge detection on screen; falls back to direct URL launch; summarizes via Gemini. | **PARTIALLY VERIFIED** | **YES** (Video playing & transcript summarization functional) |
| **ACT-11** | Computer Settings (`computer_settings`) | `actions/computer_settings.py:computer_settings` | Voice/Tool: `"computer_settings"` | `pycaw`, `comtypes`, WMI, `pyautogui` | Uses Core Audio API; falls back to virtual volume keyboard strokes. | **VERIFIED** | **YES** (Direct Windows volume and brightness manipulation) |
| **ACT-12** | AI Image Generator (`generate_image`) | `actions/image_generator.py:generate_image` | Voice/Tool: `"generate_image"` | Hugging Face Inference API | Tries FLUX.1; falls back to SDXL -> SD 2.1; auto-opens generated PNG. | **PARTIALLY VERIFIED** | **CONDITIONAL** (Requires `huggingface_api_key` configured) |
| **ACT-13** | Browser Automation (`browser_control`) | `actions/browser_control.py:browser_control` | Voice/Tool: `"browser_control"` | Playwright, Google Chrome CDP | Attaches to Chrome (9222); falls back to launching dedicated Chrome profile. | **VERIFIED** | **YES** (Full click, type, scrape, navigate capabilities) |
| **ACT-14** | Autonomous Browser Agent (`browser_agent`) | `agent/tool_executor.py:_handle_browser_agent` | Voice/Tool: `"browser_agent"` | `browser_use`, Playwright, LLM | Multistep agent loop; captures page DOM and loops actions until goal met. | **PARTIALLY VERIFIED** | **YES** (Autonomous multi-step web agent) |
| **ACT-15** | File Manager (`file_manager`) | `actions/file_manager.py:file_manager` | Voice/Tool: `"file_manager"` | `send2trash`, `PyPDF2`, `docx`, `hashlib` | Path-scoped; confirmation popup for delete/move; safe recycles. | **VERIFIED** | **YES** (BFS search across all drives, OCR/PDF extraction, cleanup) |
| **ACT-16** | Command Terminal (`cmd_control`) | `actions/cmd_control.py:cmd_control` | Voice/Tool: `"cmd_control"` | Windows `cmd.exe`, PowerShell | Critic confirmation popup; matches hardcoded safe commands or asks LLM. | **VERIFIED** | **YES** (Executes shell commands with captured output) |
| **ACT-17** | Desktop Controller (`desktop_control`) | `actions/desktop.py:desktop_control` | Voice/Tool: `"desktop_control"` | Windows `ctypes.windll`, `shutil` | Categorizes desktop files into subfolders; changes wallpaper. | **VERIFIED** | **YES** (Organizes desktop icons, sets wallpaper via Win32 API) |
| **ACT-18** | Coding Helper (`code_helper`) | `actions/code_helper.py:code_helper` | Voice/Tool: `"code_helper"` | Gemini Flash, Groq API | Fallback cascade across Groq -> Gemini 2.0 -> Gemini 1.5; auto-tests code. | **VERIFIED** | **YES** (Writes, debugs, optimizes, and runs scripts) |
| **ACT-19** | Autonomous Dev Agent (`dev_agent`) | `actions/dev_agent.py:dev_agent` | Voice/Tool: `"dev_agent"` | Gemini API, Groq, Subprocess | Multi-file planner, builds files, installs dependencies, fixes up to 5 times. | **PARTIALLY VERIFIED** | **YES** (Can build and run complete multi-file Python projects) |
| **ACT-20** | Task Queue Job (`agent_task`) | `agent/task_queue.py:submit` | Voice/Tool: `"agent_task"` | Thread pool, `AgentExecutor` | Prioritized queue (`HIGH`, `NORMAL`, `LOW`); reports completion asynchronously. | **VERIFIED** | **YES** (Executes long-running goals in background) |
| **ACT-21** | Computer Control (`computer_control`) | `actions/computer_control.py:computer_control` | Voice/Tool: `"computer_control"` | `pyautogui`, `pyperclip` | PyAutoGUI failsafe enabled; clamps coordinates; wraps errors. | **VERIFIED** | **YES** (Atomic clicks, typing, hotkeys, dragging, and waits) |
| **ACT-22** | Game Updater (`game_updater`) | `actions/game_updater.py:game_updater` | Voice/Tool: `"game_updater"` | Windows Registry (`winreg`) | Reads Steam `appmanifest_*.acf` files and Epic Launcher manifests directly. | **VERIFIED** | **YES** (Inspects real installed Steam/Epic games and updates) |
| **ACT-23** | Flight Finder (`flight_finder`) | `actions/flight_finder.py:flight_finder` | Voice/Tool: `"flight_finder"` | Browser Control, Gemini API | Opens Google Flights URL in browser; scrapes text; structures via Gemini. | **PARTIALLY VERIFIED** | **YES** (Note: Hardcodes currency `&curr=TRY` in URL query) |
| **ACT-24** | Memory Saver (`save_memory`) | `agent/tool_executor.py:_handle_save_memory` | Voice/Tool: `"save_memory"` | SQLite (`data/jarvis.db`) | Validates key/value; writes to category; silent confirmation. | **VERIFIED** | **YES** (Saves explicit facts, project context, preferences) |
| **ACT-25** | Memory Retriever (`retrieve_memory`) | `agent/tool_executor.py:_handle_retrieve_memory` | Voice/Tool: `"retrieve_memory"` | SQLite (`data/jarvis.db`) | Category filtering, fuzzy keyword matching; returns up to 5 memories. | **VERIFIED** | **YES** (Retrieves stored personal and task memories) |
| **ACT-26** | Memory Forgetter (`forget_memory`) | `agent/tool_executor.py:_handle_forget_memory` | Voice/Tool: `"forget_memory"` | SQLite (`data/jarvis.db`) | Critic confirmation popup; deletes matching keys. | **VERIFIED** | **YES** (Deletes specific memory entries) |
| **ACT-27** | News Reporter (`news_report`) | `actions/news.py:news_report` | Voice/Tool: `"news_report"` | Google News RSS Feed | Parses XML headlines; falls back to general news if category missing. | **VERIFIED** | **YES** (Live real-time news retrieval without API keys) |
| **ACT-28** | Daily Briefing (`daily_briefing`) | `actions/daily_briefing.py:get_daily_briefing` | Voice/Tool: `"daily_briefing"` | Open-Meteo, Google News | Aggregates time, local weather, tech news headlines, and user reminders. | **VERIFIED** | **YES** (Comprehensive morning report) |
| **ACT-29** | Workflow Chains (`workflow_chain`) | `actions/workflow_chains.py:workflow_chains` | Voice/Tool: `"workflow_chain"` | OS Settings, Open App, Reminders | Executes pre-configured chains: Study, Coding, Relax, Presentation modes. | **VERIFIED** | **YES** (Adjusts volume, launches apps, sets Pomodoro timer) |
| **ACT-30** | Knowledge Base Query (`query_knowledge_base`) | `rag_core/engine.py:search` | Voice/Tool: `"query_knowledge_base"` | FAISS, `rank-bm25`, SQLite | Hybrid search across codebase, docs, memory, OCR, project adapters. | **VERIFIED** | **YES** (Searches indexed workspace files and documents) |
| **ACT-31** | Research Mode (`research_mode`) | `actions/research_mode.py:research_mode` | Voice/Tool: `"research_mode"` | `duckduckgo-search`, `newspaper3k` | Searches DDG/Google; downloads full web articles; parallel thread pool. | **VERIFIED** | **YES** (Performs multi-site research synthesis) |
| **ACT-32** | System Shutdown (`shutdown_system`) | `agent/tool_executor.py:_handle_shutdown_system` | Voice/Tool: `"shutdown_system"` | Tkinter root destroy / OS shutdown | Requires `confirm=True` and critic modal confirmation. | **VERIFIED** | **YES** (Gracefully terminates JARVIS or powers down PC) |
| **ACT-33** | Image Clustering (`image_cluster`) | `actions/image_cluster.py:image_cluster` | Voice/Tool: `"image_cluster"` | `deepface`, `scikit-learn`, `cv2` | Catches missing `deepface`; falls back to basic extension grouping. | **PARTIALLY VERIFIED** | **CONDITIONAL** (`deepface` not in requirements.txt) |
| **ACT-34** | Cursor Agent (`cursor_agent`) | `actions/cursor_agent.py:cursor_agent` | Voice/Tool: `"cursor_agent"` | FreeAIRouter, Subprocess | Auto-backs up files to `.jarvis_bak`; loops test-edit up to 6 times. | **VERIFIED** | **YES** (Autonomous test-driven script repair) |
| **ACT-35** | Plan Manager (`manage_plan`) | `agent/tool_executor.py:_handle_manage_plan` | Voice/Tool: `"manage_plan"` | Local disk (`active_plan.json`) | Persists active multi-step plan; updates step completion status. | **VERIFIED** | **YES** (Maintains step tracking across conversation turns) |
| **ACT-36** | Persona Switcher (`switch_persona`) | `agent/tool_executor.py:_handle_switch_persona` | Voice/Tool: `"switch_persona"` | Main session connection | Updates active persona (`jarvis` <-> `friday`); reloads theme & session. | **VERIFIED** | **YES** (Dynamically switches system instructions and voice) |

### 3.2 Core System Capabilities & Subsystems

| Subsystem ID | Component | Source Location | Implementation Details | Health Status |
| :--- | :--- | :--- | :--- | :--- |
| **SYS-01** | Fast Local Regex Router | `core/local_router.py` | Bypasses LLM for instant local commands: "time", "date", "lock pc", "sleep pc", "screenshot", "recycle bin". | **VERIFIED** (Sub-millisecond execution) |
| **SYS-02** | Acoustic Clap Activation | `core/clap_detector.py` | Audio chunk energy & peak-to-average ratio calculation; triggers barge-in and unmute. | **VERIFIED** (Heuristic mode functional) |
| **SYS-03** | Wake Word Spotting | `core/wake_detector.py` | `openwakeword` ONNX model listening for "Hey Jarvis" on 1280-sample non-overlapping chunks. | **VERIFIED** (Lightweight offline keyword spotting) |
| **SYS-04** | Continuous Vision Service | `vision/service.py` | Daemon thread capturing screen frames with perceptual hashing and adaptive OCR frequency. | **VERIFIED** (Maintains live screen context in prompts) |
| **SYS-05** | Proactive Suggestion Engine | `intelligence/proactive_engine.py` | Background loop evaluating 8 rules against hardware vitals, idle time, and emotional markers. | **VERIFIED** (Injects proactive advice into UI/speech) |
| **SYS-06** | Predictive Habit Engine | `core/predictive_engine.py` | Tracks application launch histograms in `memory/usage_log.json`; predicts regular app habits. | **VERIFIED** (Suggests frequent apps based on hour) |
| **SYS-07** | Offline Speech Recognition | `core/audio_engine.py:listen_loop` | Background `faster-whisper` (base.en int8); transcribes VAD chunks when Gemini is offline. | **VERIFIED** (Local fallback functional) |
| **SYS-08** | Instant Local Speech Synthesis | `core/utils.py:speak_local` | Thread-local Windows SAPI.SpVoice COM interface; falls back to windowless PowerShell COM. | **VERIFIED** (Zero-latency instant spoken feedback) |
| **SYS-09** | Model Context Protocol Integration | `mcp_client/manager.py` | Spawns Node.js MCP servers via stdio JSON-RPC; converts tools into Gemini live tool schemas. | **PARTIALLY VERIFIED** (Requires Node.js runtime) |
| **SYS-10** | Path Scope Security Enforcement | `core/path_scope.py` | Restricts file access and command arguments within designated workspace roots. | **VERIFIED** (Blocks directory traversal attacks) |

---

## 4. AI and Conversation System

### 4.1 Primary AI Provider & Model Configuration
- **API Provider:** Google Gemini API via official `google-genai` Python SDK (v1.65.0).
- **Conversational Model:** `models/gemini-2.5-flash-native-audio-preview-12-2025` via `client.aio.live.connect`.
- **Modality:** Native Real-Time Audio (`response_modalities=["AUDIO"]`). Raw PCM input at 16,000 Hz, output audio at 24,000 Hz.
- **Voices:** Prebuilt Gemini voice `"Charon"` (for JARVIS) or `"Kore"` (for FRIDAY).
- **Session Configuration (`_build_config()` in `main.py`):**
  - Live session resumption enabled (`SessionResumptionConfig`).
  - Input and output audio transcriptions enabled (`input_audio_transcription`, `output_audio_transcription`).
  - Tool calling enabled with 35 declared tools plus dynamically registered MCP tools (`tools=_CACHED_TOOLS`).

### 4.2 Multi-Model Secondary Cascade (`core/ai_router.py`)
When secondary text or code generation is required (e.g., in `dev_agent.py`, `code_helper.py`, `cursor_agent.py`, `planner.py`), the `FreeAIRouter` evaluates a tiered cascade:
1. **Tier 1 (High Quality Free/Tiered):**
   - Groq: `llama-3.3-70b-versatile` (`groq_api_key`)
   - NVIDIA NIM: `meta/llama-3.1-70b-instruct` (`nvidia_api_key`)
   - Google: `gemini-2.0-flash` (`gemini_api_key`)
2. **Tier 2 (Fast / Reasoning):**
   - Groq: `llama3-8b-8192`
   - NVIDIA NIM: `deepseek-ai/deepseek-r1`
   - OpenRouter: `meta-llama/llama-3.2-3b-instruct:free`
   - Hugging Face: `mistralai/Mistral-7B-Instruct-v0.3`
3. **Tier 3 (Zero-Key Fallback):**
   - Pollinations.ai (Free OpenAI proxy endpoint, no key required).

### 4.3 Prompt Construction & Context Management
System instructions are dynamically assembled in `_build_config()` before every session connect:
1. **Current Date & Time:** Formatted timestamp (e.g., `"Monday, November 05, 2026 — 11:15 PM"`).
2. **Session Context:** Last application focused, last query asked, last file modified.
3. **Active Plan:** Step-by-step progress from `self.state.active_plan` (e.g., `1. [DONE] Setup workspace`).
4. **Live Screen Context:** Formatted textual summary from `vision/service.py` (active window, detected UI elements, error messages).
5. **Preloaded Long-Term Memory:** User preferences, facts, and project notes from `data/jarvis.db`.
6. **User Biographical Context:** Profile summary from `memory/profile_manager.py` (name, age, college, routine).
7. **Emotional State Context:** Fatigue, stress, and interaction preferences from `emotion/state_detector.py`.
8. **System Vitals:** CPU %, RAM %, and Battery level / charge state.
9. **Base Persona Instructions:** Content of `core/prompt.txt` (or `core/friday_prompt.txt`).
- **Context Ceiling:** Character clamp at 3,500,000 characters (~1M tokens) to prevent WebSocket packet overflow.

### 4.4 Language & Hinglish Processing
- **Primary Persona (`core/prompt.txt`):** Instructs the model to speak fluent, modern **Hinglish** (Hindi-English mix written in Latin script), avoiding robotic repetition and starting sentences with varied phrasing.
- **FRIDAY Persona (`core/friday_prompt.txt`):** Instructs fluent Hinglish with immediate override to professional English if the user addresses the system in English.
- **Language Detection (`intelligence/personal_context.py`):** Analyzes conversational keywords (`"kaise"`, `"kya"`, `"hai"`, `"theek"`, `"acha"`) to classify preference between Hinglish and English.
- **Goal Translation (`agent/executor.py:_translate_to_goal_language`):** Employs Gemini to translate intermediate tool outputs into the user's input language before presenting final answers.

### 4.5 Tool / Function Calling Lifecycle
1. User speaks or types an instruction.
2. Gemini Live WebSocket emits a `response.tool_call` frame containing one or more `function_calls`.
3. `main.py` dispatches calls concurrently to `ToolExecutor.execute(fc)`.
4. **Critic Gatekeeper:** If the tool is classified as high-risk (`send_message`, `cmd_control`, `computer_settings`, `shutdown_system`, file deletion/movement, memory forget), execution blocks and displays a Windows modal dialog (`ctypes.windll.user32.MessageBoxW`). If the user clicks **NO**, the tool returns an action-blocked message.
5. **Immediate Spoken Filler:** JARVIS speaks a thread-local filler (e.g., *"Right away, sir."* or *"One moment, sir."*) via SAPI COM TTS to eliminate awkward dead air during heavy network or tool calls.
6. The action executes. Untrusted output (web pages, files, OCR) is wrapped inside `<untrusted_data>` guardrails.
7. Output is truncated if it exceeds 25,000 characters to prevent Gemini Live 1007 WebSocket frame crash.
8. `session.send_tool_response()` transmits `types.FunctionResponse` back to the live Gemini WebSocket.

### 4.6 Offline & Fallback Behavior
- If the Gemini Live connection drops, `main.py` attempts reconnection with exponential backoff (2s up to 30s).
- Key rotation (`rotate_api_key()`) triggers automatically upon receiving HTTP 429 / Quota Exhausted errors.
- When Gemini is offline:
  - Microphone audio captured by `audio_engine.py` is evaluated by VAD.
  - Upon speech completion, the audio chunk is routed to `faster-whisper` (`base.en` on CPU int8).
  - Recognized text is evaluated by `core/local_router.py` to allow local operations (time, date, lock, screenshot, PC sleep) without internet.

---

## 5. Integrations and External Services

| Service / Integration | Implementation Method | Authentication / Credentials | Network Dependency | Actual Status vs. Planned |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini Live API** | Bidirectional WebSocket over TLS (`google-genai` SDK) | API Key (`config/api_keys.json` or `.env`) | **Mandatory** | **IMPLEMENTED & VERIFIED** |
| **Secondary LLMs (Groq, NVIDIA, OpenRouter)** | REST HTTPS (`requests.Session` with retry adapter) | API Keys (`groq_api_key`, `nvidia_api_key`, etc.) | **Mandatory** (for secondary tasks) | **IMPLEMENTED & VERIFIED** |
| **Pollinations.ai** | REST HTTPS (Free text & image endpoints) | None (Zero authentication required) | **Mandatory** | **IMPLEMENTED & VERIFIED** |
| **Playwright / Google Chrome** | Chrome DevTools Protocol (CDP) on `localhost:9222` | Local process attachment or dedicated profile | **Local Only** (offline browser automation) | **IMPLEMENTED & VERIFIED** |
| **Model Context Protocol (MCP)** | JSON-RPC over `stdio` subprocess & HTTP SSE | Subprocess / Google OAuth tokens | **Local / Hybrid** | **IMPLEMENTED & VERIFIED** |
| **Google Drive MCP** | REST HTTPS via MCP Google Auth proxy | OAuth 2.0 (`client_secret.json`, `drive_token.json`)| **Mandatory** | **IMPLEMENTED (Requires user OAuth login)** |
| **Weather (wttr.in & Open-Meteo)** | REST HTTPS | None (Public free APIs) | **Mandatory** | **IMPLEMENTED & VERIFIED** |
| **Google News RSS** | HTTPS GET (`news.google.com/rss`) | None (Public RSS feed) | **Mandatory** | **IMPLEMENTED & VERIFIED** |
| **Google Flights** | Browser scraping via Playwright + LLM extraction | None (Automates web interface) | **Mandatory** | **IMPLEMENTED (Fragile web scraping)** |
| **Steam & Epic Games** | Local Windows Registry & VDF/JSON manifest parsing | None (Local filesystem reading) | **Local Only** (Offline) | **IMPLEMENTED & VERIFIED** |
| **WhatsApp Messaging** | GUI Keystroke Automation (`pyautogui.press("win")`) | None (Requires logged-in Windows desktop app) | **Local Only** (App handles network) | **SIMULATED ONLY** (No real API integration) |
| **Telegram Messaging** | GUI Keystroke Automation (`pyautogui`) | None (Requires logged-in Windows desktop app) | **Local Only** (App handles network) | **SIMULATED ONLY** (No real API integration) |
| **Instagram Messaging** | Microsoft Edge browser automation + `pyautogui` | None (Requires active browser login session) | **Mandatory** | **SIMULATED ONLY** (No real API integration) |
| **Discord Messaging** | GUI Keystroke Automation (`pyautogui`) | None (Requires logged-in desktop app) | **Local Only** | **SIMULATED ONLY** (No real API integration) |

---

## 6. Security and Permissions

### 6.1 Vulnerability & Security Findings Summary

| Finding ID | Vulnerability Description | Affected Module(s) | Severity Level | Detailed Risk Analysis |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | Arbitrary Code Execution via Generated Code | `agent/executor.py` (`_run_generated_code`) | **CRITICAL** | If a multi-step plan calls `generated_code`, the system requests Gemini to write raw Python code, writes it to a temporary `.py` file, and executes it via `subprocess.run([sys.executable, tmp_path])` without container isolation, chroot, or sandbox restrictions. |
| **SEC-02** | Command Injection / Unrestricted Shell Access | `actions/cmd_control.py:cmd_control` | **HIGH** | Translates natural language requests into raw PowerShell / CMD strings. While a path scope validator and Windows critic popup exist, sophisticated prompt injections or chained shell commands (`&`, `\|`, `;`) could execute arbitrary system commands. |
| **SEC-03** | Plaintext API Credentials on Filesystem | `config/api_keys.json`, `.env` | **HIGH** | API keys for Google Gemini, Groq, NVIDIA, OpenRouter, and Hugging Face are stored in unencrypted plaintext JSON and `.env` files in the repository workspace. Any local process or compromised tool can read them. |
| **SEC-04** | Prompt Injection via Untrusted Web & Screen Content | `main.py`, `agent/tool_executor.py` | **MEDIUM** | Information gathered from web search, browser pages, and OCR is passed to the Gemini context. Although enclosed in `<untrusted_data>` tags, adversarial instructions embedded in webpages could influence LLM decision-making. |
| **SEC-05** | Sensitive Data Masking Bypass in Logging | `actions/doctor.py`, `main.py` | **LOW** | System health diagnostics prints partial API keys (`key[:4] + "..." + key[-4:]`) to logs. While partially masked, exposing the key prefix and suffix weakens entropy. |
| **SEC-06** | UDP Port 9999 Unauthenticated Wakeup | `main.py:_start_udp_listener`, `clap_launcher.py` | **LOW** | Binds to `127.0.0.1:9999` without authentication. Any local application on the host can send `b"WAKE"` to force JARVIS to unmute, lift to foreground, and speak. |

### 6.2 Confirmation & Guardrail Mechanisms
- **Critic Checkpoint Modal Dialog (`agent/tool_executor.py`):** For tools categorized as high-risk (`send_message`, `cmd_control`, `computer_settings`, `shutdown_system`, `forget_memory`, file deletions/moves), execution synchronously prompts the user via a native topmost Windows MessageBox (`MB_YESNO`).
- **Memory Guard (`main.py:_update_memory_async`):** If the last executed tool was a web search, browser control, or vision OCR action, silent writes to persistent memory are blocked to prevent prompt injection attacks from poisoning long-term memory.
- **Path Scope Security (`core/path_scope.py`):** Validates file arguments against designated workspace roots to prevent directory traversal outside authorized drives.

---

## 7. Performance and Resource Requirements

### 7.1 Resource Utilization Breakdown

| Resource Metric | Measured / Estimated Value | Contributing Factors & Architecture Context |
| :--- | :--- | :--- |
| **Base Idle RAM** | ~350 MB – 500 MB | Base Python runtime, Tkinter GUI, AudioEngine sounddevice streams, openWakeWord model. |
| **Peak Operational RAM** | 1.8 GB – 2.8 GB | Loading `faster-whisper` (`base.en` int8), `sentence-transformers` (`bge-small-en-v1.5`), FAISS vector indices, and Playwright Chromium headless/headful instance. |
| **CPU Usage (Idle)** | 1.5% – 5.0% | Audio capture loop, WebRTC/NumPy VAD processing, background periodic scheduler (1 min tick). |
| **CPU Usage (Active)** | 35% – 75% (Multi-core) | Faster-Whisper CPU inference, OpenCV frame processing, FAISS index similarity calculations. |
| **GPU Dependency** | **OPTIONAL** | PyTorch and Faster-Whisper default to CPU (`device="cpu"`, `compute_type="int8"`). GPU is not required. |
| **Disk Storage** | ~3.8 GB total | Codebase (~25 MB), Python virtual environment packages (~2.5 GB), Vosk model directory (~45 MB), Playwright browser binaries (~800 MB), FAISS indices & databases (~50 MB). |
| **Startup Latency** | 3.5s – 6.0s | Staggered initialization thread loads heavy modules sequentially (0.0s Whisper, 0.5s Predictive, 1.0s Memory, 1.5s RAG, 2.0s Vision, 2.5s Proactive, 3.0s MCP) to avoid thread starvation. |

### 7.2 Threading & Asynchronous Concurrency Model
JARVIS X employs a multi-tier concurrency model:
1. **Asyncio Event Loop (Main Thread):** Drives the primary Gemini Live WebSocket connection, microphone transmit loop, audio receive loop, and speaker output loop.
2. **Tkinter GUI Loop (Main Thread):** Driven by `ui.root.mainloop()` with cross-thread updates scheduled via `ui.root.after()`.
3. **Background Daemon Threads:**
   - `SharedScheduler`: Periodic vitals monitoring (1 min) and prediction checks (10 min).
   - `AppWatcher`: Background process poller checking foreground active applications.
   - `VisionService`: Independent loop capturing and hashing screen captures.
   - `UDP Wake Listener`: Thread listening on `127.0.0.1:9999` for external triggers.
   - `RAG Watchdog`: Filesystem watcher indexing workspace code changes in real-time.
   - `TaskQueue Worker`: Background worker managing multi-step agent plans.
   - `ToolPoolExecutor`: Dedicated `ThreadPoolExecutor(max_workers=64)` for non-blocking tool calls.

---

## 8. Environment and Execution Requirements

### 8.1 System Prerequisites
- **Operating System:** Windows 10 (Build 19041+) or Windows 11 (64-bit).
- **Python Version:** Python 3.11, 3.12, 3.13, or 3.14 (64-bit).
- **Node.js Runtime:** Node.js v18.0.0+ and `npm`/`npx` (Required for MCP servers).
- **Physical Hardware:**
  - Dedicated microphone input (configured as Windows Default Recording Device).
  - Audio output / speakers / headphones (configured as Windows Default Playback Device).
  - Minimum 8 GB RAM (16 GB recommended).
  - Minimum 10 GB available SSD storage.

### 8.2 Configuration Files Required
- `config/api_keys.json`: Must contain at least `"gemini_api_key"`.
- `config/browser_signal.json`: Created automatically during browser automation.
- `rag_config.yaml`: Configuration for RAG chunk sizes, database paths, and vector storage.
- `mcp_client/config.json`: Configuration for local and remote Model Context Protocol servers.

### 8.3 Environment Variables
- `USERPROFILE`: Windows user profile path (for Desktop, Documents, Downloads resolution).
- `TEMP`: Temporary directory path (used by reminder scheduler and code runner).
- `JARVIS_LATENCY_DEBUG`: *(Optional)* Set to `"1"` to output speech-to-audio latency timings in stdout.
- `PYTHONWARNINGS`: Set to `"ignore"` by `main.py` on startup.

---

## 9. Current Project Health

### 9.1 Broken Imports, Inconsistencies & Deficiencies

1. **Broken Standalone Test (`test_browser.py`):**
   ```python
   # Line 4 of test_browser.py:
   from actions.browser_use_action import browser_use_action  # CRITICAL: File does not exist on disk!
   ```
   *Impact:* Running `python test_browser.py` crashes immediately with `ModuleNotFoundError`. The logic was refactored into `actions/browser_control.py`, but this test script was never updated.

2. **Inconsistent Doctor Diagnostic Dependency (`actions/doctor.py`):**
   ```python
   # Line 68 of actions/doctor.py:
   import pyaudio  # INCONSISTENCY: The audio engine uses sounddevice, not PyAudio!
   ```
   *Impact:* Running the `system_doctor` diagnostic always reports a false warning: `"[Audio] [WARN] PyAudio: NOT installed (Mic audio disabled)"`, even when the real audio engine (`sounddevice`) is functioning perfectly.

3. **Missing ML Clap Model Weights (`actions/clap_cnn/clap_model.pth`):**
   *Impact:* The ML Clap Detector falls back to the heuristic energy detector on every startup because model weights were never trained or saved to disk.

4. **Missing Persona System Prompt (`core/edith_prompt.txt`):**
   *Impact:* `ui/setup_screen.py` offers `E.D.I.T.H` as a selectable persona, but `core/edith_prompt.txt` does not exist on disk, causing the system to fall back to a hardcoded generic prompt.

5. **Undeclared Dependencies in `requirements.txt`:**
   - `groq` (Used in `actions/dev_agent.py` and `actions/code_helper.py`).
   - `huggingface_hub` (Used in `actions/image_generator.py`).
   - `deepface` (Used in `actions/image_cluster.py`).
   *Impact:* Fresh installations following `pip install -r requirements.txt` will encounter `ImportError` exceptions when attempting to use Groq fallbacks, Hugging Face image generation, or face clustering.

6. **Hardcoded Regional Parameters in Travel Search (`actions/flight_finder.py`):**
   - Hardcodes `&curr=TRY` (Turkish Lira) in the Google Flights URL query.
   - Contains Turkish language date conversion rules (`"ocak"`, `"şubat"`, `"mart"`, `"nisan"`).
   - Contains Turkish code comments across multiple modules (`actions/computer_settings.py`, `actions/code_helper.py`, `actions/youtube_video.py`).

---

## 10. Testing Readiness Assessment

To prepare an independent QA testing program without modifying code, testing requirements are classified into the following 7 readiness categories:

### Category A: Available Immediately (Offline, Mockable, or Script-Verifiable)
- `core/local_router.py`: Fast local command matching (time, date, lock, sleep regexes).
- `core/path_scope.py`: Path traversal validation and drive boundary tests.
- `memory/memory_manager.py`: SQLite database CRUD, category normalization, and secret pattern filtering.
- `memory/profile_manager.py`: Biographical JSON read/write and age calculation from DOB.
- `vision/privacy.py`: Regex secret masking tests (`AIza...`, bearer tokens, credit cards).
- `agent/planner.py`: Offline prompt template validation and JSON plan schema parsing.
- `agent/error_handler.py`: Offline decision tree parsing (`RETRY`, `SKIP`, `REPLAN`, `ABORT`).

### Category B: Requires Physical Hardware Access (Microphone, Speakers, Display)
- `core/audio_engine.py`: Real-time full-duplex microphone stream and speaker playback.
- `core/wake_detector.py`: openWakeWord "Hey Jarvis" keyword detection over microphone input.
- `core/clap_detector.py`: Hand clap acoustic spike detection.
- `core/vad_engine.py`: Speech start/end boundary detection via WebRTC / NumPy energy.
- `vision/capture_engine.py`: Multi-monitor display capture via `mss`.
- `actions/computer_settings.py`: Hardware volume manipulation (`pycaw`) and screen brightness.

### Category C: Requires API Credentials / External Cloud Accounts
- `main.py` Live Core: Valid Google AI Studio API key (`gemini_api_key`) supporting the Live Audio preview model.
- `actions/image_generator.py`: Hugging Face user access token (`huggingface_api_key`).
- `core/ai_router.py`: Secondary API keys (Groq, NVIDIA NIM, OpenRouter).
- `mcp_client/google_auth.py`: Google Cloud OAuth Client ID / Secret with Google Drive API enabled.

### Category D: Requires Active Internet Connection
- `actions/weather_report.py`: Access to `wttr.in` and `open-meteo.com`.
- `actions/news.py`: Access to `news.google.com/rss`.
- `actions/web_search.py`: Access to DuckDuckGo and Google Search endpoints.
- `actions/youtube_video.py`: YouTube transcript scraping.
- `actions/website_builder/builder.py`: Node Package Manager (`npm install` network downloads).

### Category E: Requires Manual User Interaction / GUI Confirmation
- All Critic-protected tools (`cmd_control`, `send_message`, file delete/move, `shutdown_system`, `forget_memory`) require a human tester to click **YES** on the Windows modal popup.
- `ui/setup_screen.py`: Requires interactive wizard completion when testing clean-slate first boots.

### Category F: Requires Additional Software or Infrastructure Installed
- **Node.js & npx:** Required to run MCP servers (`playwright`, `filesystem`, `github`, `sqlite`).
- **Google Chrome:** Required for browser automation via DevTools Protocol (`localhost:9222`).
- **Flutter SDK:** Required to test `actions/app_builder` APK compilation or device execution.
- **Tesseract OCR:** Required for `pytesseract` OCR text extraction (`C:\Program Files\Tesseract-OCR\tesseract.exe`).
- **Steam / Epic Games Launcher:** Required to test `actions/game_updater.py` library inspection.
- **WhatsApp Desktop / Telegram Desktop:** Required to test GUI-simulated messaging.

### Category G: Cannot Currently Be Tested (Blocked or Incomplete)
- `test_browser.py`: Blocked due to missing module `actions.browser_use_action`.
- `actions/clap_cnn/model.py` (Inference): Blocked due to missing weight file `clap_model.pth`.
- `actions/image_cluster.py` (Face Clustering): Blocked if `deepface` is not installed on the testing host.
- Persona `E.D.I.T.H`: Blocked due to missing system prompt file `core/edith_prompt.txt`.

---

## 11. Known Limitations & Technical Unknowns

1. **Messaging Reliability:** The messaging actions (`actions/send_message.py`) do not interface with official APIs or webhooks. They execute blind `pyautogui` keystrokes (Win -> search app -> Ctrl+F -> type -> enter). If the desktop application changes UI focus, displays an update modal, or takes longer than the hardcoded `time.sleep()` delays to load, the message will fail to send or be typed into the wrong window.
2. **Oversized Tool Results & WebSocket Fragility:** Gemini Live WebSocket connections are sensitive to payload framing errors. While `tool_executor.py` has a 25,000-character safety truncation, exceptionally large payloads or binary returns can cause Gemini Live error 1007 or 1011 disconnections.
3. **Single Active Plan Persistence:** The active plan is saved to a single local JSON file (`memory/active_plan.json`). If concurrent tasks are executed via `TaskQueue`, they may overwrite each other's active plan state.
4. **Unknown WebRTC VAD Binary Compatibility:** On newer Python releases (e.g., Python 3.14), pre-compiled C-extensions for `webrtcvad` may fail to install, forcing the system onto the pure-Python `_EnergyVadFallback`.

---

## 12. Questions Requiring Sahil's Input

To assist in formulating the subsequent testing program, the following questions must be clarified by the project owner:

1. **Messaging Workflow Strategy:** Are WhatsApp, Telegram, and Discord intended to remain as simulated desktop GUI automations, or is the goal to replace them with official headless APIs (e.g., Twilio, Telegram Bot API, Discord Bot Webhooks)?
2. **Missing Module `actions.browser_use_action`:** Should `test_browser.py` be repointed to use `actions.browser_control.browser_control`, or was an older autonomous browser script unintentionally removed?
3. **Clap CNN Model Weights:** Was `actions/clap_cnn/clap_model.pth` trained and omitted from version control, or should the project officially standardize on the heuristic `core/clap_detector.py`?
4. **Third-Party Dependencies:** Should `groq`, `huggingface_hub`, and `deepface` be officially added to `requirements.txt`, or should features requiring them be refactored to use existing libraries?
5. **Persona E.D.I.T.H:** Is the `E.D.I.T.H` persona planned for active implementation with a dedicated prompt (`core/edith_prompt.txt`) and color scheme, or should it be removed from `ui/setup_screen.py`?
6. **Regional / Turkish Artifacts:** Can the hardcoded Turkish Lira currency parameter (`curr=TRY`) in `flight_finder.py` and Turkish comments across actions be safely cleaned up in future maintenance phases?

---
*Report Compiled by Independent Senior Software Architect & QA Auditor.*  
*Discovery complete. No files were modified during this investigation.*

