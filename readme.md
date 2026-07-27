# 🤖 J.A.R.V.I.S. (MARK XXXV)

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue.svg)](https://www.microsoft.com/windows)
[![AI: Gemini 2.0 / 2.5 Flash](https://img.shields.io/badge/AI-Gemini%202.5--Flash-orange.svg)](https://aistudio.google.com/)

### **The Next-Generation Autonomous Voice AI Assistant & System Copilot — By Sahil Sheikh**

**J.A.R.V.I.S.** (*Just A Rather Very Intelligent System*) is a real-time, voice-driven AI assistant and autonomous agent system. It **hears** your voice, **sees** your screen, **understands** complex multi-step instructions, **maintains long-term memory**, and **controls** your Windows PC.

---

## ✨ System Architecture & Key Capabilities

```
                  ┌──────────────────────────────────────────────┐
                  │                 J.A.R.V.I.S.                 │
                  └──────────────────────┬───────────────────────┘
                                         │
     ┌───────────────────┬───────────────┼───────────────┬───────────────────┐
     ▼                   ▼               ▼               ▼                   ▼
🎙️ Audio Engine      🧠 RAG Core     🤖 Agent Core   💡 Intelligence     🖥️ Modern UI
 • OpenWakeWord      • FAISS Vector  • Planner       • Proactive Engine  • Live Waveform
 • Vosk Fallback     • BM25 Hybrid   • Task Queue    • Companion Mode    • Quick Controls
 • WebRTC/NumPy VAD  • Watchdog      • Tool Exec     • Rules & Context   • Status Logs
 • Local SAPI TTS    • Code/Docs/Web • Self-Healing  • History Tracker   • Voice / Text
```

### 1. 🎙️ Real-Time Audio & Voice Engine
- **Dual Wake Word Detector**: Uses `openwakeword` with local `vosk` model fallback.
- **Voice Activity Detection (VAD)**: Google WebRTC VAD with a built-in pure-Python/NumPy RMS energy fallback for zero-dependency operation across Python versions (Python 3.11 to 3.14+).
- **ML Clap Detector**: Custom `ClapCNN` deep learning model to trigger custom actions on hand claps.
- **Ultra-Fast Local TTS**: Instant SAPI COM thread-local speech synthesis fallback.
- **Local STT Fallback**: Integrated `Faster-Whisper` model for offline speech recognition when Gemini connectivity is unavailable.

### 2. 🧠 RAG Core Engine (Retrieval-Augmented Generation)
- **Hybrid Retrieval**: Combines BM25 keyword search with FAISS dense vector embeddings and SQLite metadata (`rag_metadata.db`).
- **Domain Adapters**: Specialized adapters for Codebase (`code_adapter`), Documents (`docs_adapter`), Web Content (`web_adapter`), Memory (`memory_adapter`), OCR (`ocr_adapter`), and Project Trees (`project_adapter`).
- **Real-Time Indexer Watchdog**: Background file watcher (`indexer.py`) that incrementally indexes codebase and workspace changes in real-time.

### 3. 🤖 Agent Core & Tool Execution System
- **Autonomous Planner & Task Queue**: Multi-step reasoning pipeline (`planner.py`, `task_queue.py`) for breaking down complex user prompts into executable tool chains.
- **Self-Healing Error Handler**: Analyzes execution exceptions dynamically (`error_handler.py`) and generates recovery strategies automatically.
- **Extensible Action Tools**:
  - 🌐 **Browser Agent & Control**: Full Playwright browser automation and web search.
  - 🛠️ **AI Website Builder**: Generates full-stack web applications dynamically.
  - 📱 **AI App Builder**: Generates mobile Flutter app code and builds native packages.
  - 💻 **Computer & Terminal Control**: Command execution, file manager, system settings, desktop control.
  - 👁️ **Screen Vision**: Real-time screenshot inspection, OCR text extraction, visual layout analysis.
  - 🕹️ **Gaming Integration**: Manages Steam and Epic Games libraries, launcher updates, and games.
  - ✈️ **Flight Finder & Research**: Live travel searches, flight tracking, and deep web research mode.
  - 📰 **Daily Briefing & News**: Automated morning briefing, weather reports, news summaries.
  - 📷 **Image Cluster**: Facial recognition and visual image grouping via deep learning embeddings.

### 4. 💡 Intelligence & Companion System
- **Proactive Engine**: Runs background event loops to monitor system state, todo list, and suggest timely actions.
- **Companion Engine & Emotion State**: Empathetic conversation analysis (`companion_engine.py`) and state detection.
- **Personal Context & Memory Manager**: Persistent JSON/FAISS semantic memory storage (`memory_manager.py`, `semantic_memory.py`, `profile_manager.py`) preserving user preferences, profile, emotional patterns, and conversation history.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **OS**: Windows 10 or Windows 11
- **Python**: Version 3.11, 3.12, 3.13, or 3.14 (Ensure "Add Python to PATH" is checked)
- **Hardware**: Standard Microphone and Speakers / Headphones

---

### 2. Installation & Setup

Open **PowerShell** or **CMD** in your project directory:

```powershell
# 1. Clone the repository
git clone https://github.com/mohammadsahil74808/Jarvis.git

# 2. Enter the directory
cd Jarvis

# 3. Create & activate a Virtual Environment (Recommended)
python -m venv venv
.\venv\Scripts\activate

# 4. Install requirements
pip install -r requirements.txt

# 5. Install Playwright browser drivers (for Web Automation & App Builders)
playwright install
```

---

### 3. Configure API Keys

1. Get a **FREE** API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Create your `config/api_keys.json` from the example template:

   ```powershell
   copy config\api_keys.json.example config\api_keys.json
   ```

3. Open `config/api_keys.json` in any text editor and insert your key:
   ```json
   {
       "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
       "groq_api_key": "",
       "nvidia_api_key": "",
       "openrouter_api_key": "",
       "hf_api_key": ""
   }
   ```

---

### 4. Launch J.A.R.V.I.S.

To start the assistant in voice & UI mode, execute:

```powershell
python main.py
```

> 💡 **Shortcut Tip:** Press **F4** at any time to toggle Microphone Mute / Unmute!

---

## 📂 Codebase Overview

```
Jarvis/
├── main.py                     # Main system entrypoint & orchestration core
├── clap_launcher.py            # Acoustic clap launcher entrypoint
├── requirements.txt            # Dependency configuration
├── rag_config.yaml             # RAG engine configuration
├── actions/                    # Action tools & autonomous capabilities
│   ├── app_builder/            # Flutter mobile application generator
│   ├── website_builder/        # Full-stack web application generator
│   ├── clap_cnn/               # Deep learning clap classification model
│   ├── browser_agent.py        # Playwright browser agent
│   ├── computer_control.py     # System automation & terminal execution
│   ├── screen_vision.py        # Visual screen inspection & OCR
│   ├── image_cluster.py        # Facial recognition image clustering
│   ├── flight_finder.py        # Travel & flight search tool
│   └── ...                     # News, weather, daily briefing, game updater
├── agent/                      # Core agent framework
│   ├── planner.py              # Multi-step reasoning planner
│   ├── task_queue.py           # Task queue management
│   ├── tool_executor.py        # Hardened tool execution dispatcher
│   └── error_handler.py        # Autonomous error recovery
├── config/                     # API keys & system settings
├── core/                       # Core engine components
│   ├── ai_router.py            # AI Router (Gemini / Local models)
│   ├── audio_engine.py         # Real-time microphone & speaker streaming
│   ├── vad_engine.py           # WebRTC / NumPy energy VAD engine
│   ├── wake_detector.py        # Dual wake word detector (OpenWakeWord/Vosk)
│   ├── clap_detector_ml.py     # ML clap detector listener
│   └── utils.py                # System utilities & SAPI local TTS
├── emotion/                    # Companion engine & emotional state analyzer
├── intelligence/               # Proactive engine, personal context & rules
├── memory/                     # Semantic memory, FAISS index & user profile
├── models/                     # Local Vosk STT models
├── rag_core/                   # RAG core, hybrid retrieval, domain adapters
└── ui/                         # Modern graphical interface (jarvis_ui.py)
```

---

## ⚡ Recent Enhancements & Optimizations

- 🧹 **Codebase Optimization**: Purged 52 unused legacy files, 10 empty folders, and 182 unused imports across 49 modules, reducing codebase size by ~3.33 MB.
- 🎙️ **Zero-Dependency VAD Engine**: Implemented an automated pure-Python/NumPy RMS energy fallback inside `vad_engine.py`, enabling instant VAD capabilities without requiring C++ compilation on Windows Python 3.14.
- 🔧 **Consolidated Utilities**: Streamlined `lazy_sd()` sounddevice initialization into `core/utils.py`.
- 🔌 **Dynamic Module Loading**: Resolved static type resolution issues with optional C extensions using `importlib`.

---

## 🎮 Keyboard Shortcuts & Controls

| Key | Action |
| :--- | :--- |
| **F4** | Mute / Unmute Microphone Input |
| **Esc** | Stop active speech output immediately |
| **Text Entry** | Type queries directly in the UI text bar |

---

## 🛡️ License

This project is licensed under **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.
- **Personal & Educational Use**: Free and encouraged!
- **Commercial Use**: Requires explicit written approval.

---

## 🤝 Connect & Support

- **Developer**: Sahil Sheikh
- **GitHub**: [@mohammadsahil74808](https://github.com/mohammadsahil74808)
- **Instagram**: [@sahil.sheikh10](https://www.instagram.com/sahil.sheikh10/)

---
*Built with ❤️ for the future of autonomous human-computer interaction.*
