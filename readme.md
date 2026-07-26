# 🤖 JARVIS (MARK XXXV)

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue.svg)](https://www.microsoft.com/windows)
[![AI: Gemini 2.0](https://img.shields.io/badge/AI-Gemini%202.0-orange.svg)](https://aistudio.google.com/)

### **The Next-Generation Personal AI Assistant — By Sahil**

**JARVIS** is an advanced, real-time voice-driven AI assistant that turns your computer into an interactive intelligent system. It can **hear** your voice, **see** your screen, **understand** complex context, and **control** your Windows PC autonomously.

---

## ✨ Key Capabilities

| Feature | Description |
| :--- | :--- |
| **🎙️ Voice-First Interaction** | Natural, low-latency conversation in multiple languages with premium TTS. |
| **🖥️ System Control** | Launch applications, manage files, and execute terminal commands effortlessly. |
| **👁️ Visual Awareness** | Full screen analysis and webcam understanding for real-time context. |
| **🧠 Persistent Memory** | Remembers your name, preferences, projects, and past interactions across sessions. |
| **🛠️ AI Builders** | Integrated **Website Builder** and **Flutter App Builder** for rapid prototyping. |
| **🕹️ Gaming Integration** | Control Steam & Epic Games — install, update, and manage your library via voice. |
| **⌨️ Hybrid Input** | Switch between voice and keyboard input at any time. |
| **🔇 One-Key Mute** | Press **F4** to instantly silence JARVIS during side conversations. |

---

## 🚀 Quick Start Guide (For New Setup / Fresh Clone)

Setting up JARVIS on a new PC or fresh clone takes just a few minutes. Follow these steps:

### 1. Prerequisites
- **OS**: Windows 10 or 11
- **Python**: Version 3.11 or 3.12 (Make sure to check "Add Python to PATH" during installation)
- **Hardware**: Working Microphone and Speakers

---

### 2. Clone & Setup

Open **CMD** or **PowerShell** and run:

```bash
# 1. Clone the repository
git clone https://github.com/mohammadsahil74808/Jarvis.git

# 2. Navigate into the project folder
cd Jarvis

# 3. (Recommended) Create and activate a Virtual Environment
python -m venv venv
venv\Scripts\activate

# 4. Install all required dependencies
pip install -r requirements.txt

# 5. Install Playwright browsers (for Web Research & AI App Builders)
playwright install
```

---

### 3. Configure API Keys

JARVIS requires a Gemini API key to operate.

1. Get a **FREE** API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Create your `config/api_keys.json` file from the provided template:

   **In PowerShell / CMD:**
   ```bash
   copy config\api_keys.json.example config\api_keys.json
   ```
3. Open `config/api_keys.json` in any text editor and paste your API key:
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

### 4. Run JARVIS

Start the assistant by running:

```bash
python main.py
```

> **Tip:** Press **F4** at any time to Mute/Unmute JARVIS microphone input!

---

## 🧠 How It Works

JARVIS is built on a modular "Agentic" architecture:
- **Core Engine**: Orchestrates voice processing, tool execution, and memory management.
- **Multi-Modal AI**: Uses **Gemini 2.0 Flash** for ultra-fast reasoning and visual understanding.
- **Tool Executor**: A hardened layer that translates AI intent into safe system actions.
- **Memory Layer**: A persistent JSON-based storage that maintains relationship and project context.

---

## 🎮 Shortcuts & Controls

- **F4 / Mute Button**: Toggles microphone input.
- **Spacebar (Hold)**: Push-to-talk (coming soon).
- **Esc**: Force stop speaking.
- **Keyboard Input**: Use the text box in the UI to type commands directly.

---

## 🛡️ License

This project is licensed under **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.
- **Personal Use**: Allowed and encouraged!
- **Commercial Use**: Prohibited without explicit permission.

---

## 🤝 Connect & Support

If you love the project, please consider giving it a ⭐ on GitHub!

- **Developer**: Sahil Sheikh
- **Instagram**: [@sahil.sheikh10](https://www.instagram.com/sahil.sheikh10/)
- **GitHub**: [mohammadsahil74808](https://github.com/mohammadsahil74808)

---
*Built with ❤️ for the future of human-computer interaction.*
