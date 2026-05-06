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
    get_base_dir, get_config, get_api_key, get_gemini_client,
    BASE_DIR, API_CONFIG_PATH, PROMPT_PATH,
    LIVE_MODEL, CHANNELS, SEND_SAMPLE_RATE,
    RECEIVE_SAMPLE_RATE, CHUNK_SIZE
)
# Heavy memory imports deferred to runtime
from core.utils import retry, async_retry

try:
    from ui.web_search_widget    import WebSearchWidget
    from ui.deep_research_widget import DeepResearchWidget
    from ui.file_search_widget   import FileSearchWidget
    _WIDGETS_OK = True
except ImportError:
    _WIDGETS_OK = False


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


from agent.tool_definitions import TOOL_DECLARATIONS


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        from agent.tool_executor import ToolExecutor
        from core.audio_engine import AudioEngine
        self.tool_executor  = ToolExecutor(self)
        self.audio_engine   = AudioEngine(self)
        self.ui.on_text_command = self._on_text_command

        # App Activity Watcher
        from core.app_watcher import AppWatcher
        self.app_watcher = AppWatcher(callback=self._on_app_activity)
        self.app_watcher.start()

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
        self._preloaded_memory = ""
        self.system_vitals = {"cpu": 0, "ram": 0, "battery": None}

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
        self.ui.root.after(5000, self._background_lazy_init)

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

        # Preload Memory
        def _preload_memory_job():
            try:
                from memory.memory_manager import load_memory, format_memory_for_prompt
                self._preloaded_memory = format_memory_for_prompt(load_memory())
                print("[JARVIS] Memory preloaded.")
            except Exception as e:
                print(f"[JARVIS] Memory preload failed: {e}")
        threading.Thread(target=_preload_memory_job, daemon=True).start()

        # System Vitals Monitor
        def _monitor_vitals():
            import psutil
            import time
            while True:
                try:
                    self.system_vitals["cpu"] = psutil.cpu_percent()
                    self.system_vitals["ram"] = psutil.virtual_memory().percent
                    bat = psutil.sensors_battery()
                    if bat:
                        self.system_vitals["battery"] = {
                            "percent": bat.percent,
                            "plugged": bat.power_plugged
                        }
                    self._config_dirty = True
                except Exception:
                    pass
                time.sleep(30)
        threading.Thread(target=_monitor_vitals, daemon=True).start()

        # Companion Engine Heartbeat (Every 15 mins)
        self.ui.root.after(900000, self._companion_heartbeat)

    def _companion_heartbeat(self):
        """Periodic check for proactive emotional engagement."""
        if self.companion_engine:
            msg = self.companion_engine.check_proactive()
            if msg:
                self.notify(msg, voice=True)
        
        self.ui.root.after(900000, self._companion_heartbeat)

    def _on_app_activity(self, opened, closed):
        """Passive watcher callback - updates context only."""
        if opened:
            self.session_context["last_app"] = opened[0]
            self.session_context["last_action"] = "opened"
            self._config_dirty = True
        if closed:
            # Optionally track closed state, but we mainly care about active context
            self._config_dirty = True

    def notify(self, text: str, voice: bool = True):
        """Proactive notification hook or internal context injector."""
        # Block proactive notifications if model is busy to prevent 1008
        if getattr(self, "tool_call_pending", False) or self._is_speaking:
            return

        if text.startswith("["):
            # Internal directive (e.g. emotional state) - send to LLM without UI/Voice prefix
            self.speak(text)
            return

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
        # Skip if model is already busy
        if getattr(self, "tool_call_pending", False) or self._is_speaking:
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

        if self._preloaded_memory:
            mem_str = self._preloaded_memory
        else:
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

        # System Vitals Context
        v_cpu = self.system_vitals.get("cpu", 0)
        v_ram = self.system_vitals.get("ram", 0)
        v_bat = self.system_vitals.get("battery")
        vitals_str = f"[SYSTEM STATUS: CPU {v_cpu}%, RAM {v_ram}%"
        if v_bat:
            vitals_str += f", Battery {v_bat['percent']}% ({'Plugged' if v_bat['plugged'] else 'On Battery'})"
        vitals_str += "]\n"
        parts.append(vitals_str)

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



    async def _receive_audio(self):
        print("[JARVIS] Recv started")
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
                                print(f"[JARVIS] Tool call: {fc.name}")
                                fr = await self.tool_executor.execute(fc)
                                fn_responses.append(fr)
                            await self.session.send_tool_response(
                                function_responses=fn_responses
                            )
                            await asyncio.sleep(0.5)
                        finally:
                            self.tool_call_pending = False
                        # ── Boş turn YOK — bu "Anladım." sorununu yaratıyordu ──

        except Exception as e:
            print(f"[JARVIS] Recv error: {e}")
            traceback.print_exc()
            raise


    async def run(self):
        client = get_gemini_client()

        first_run   = True
        local_greet = True
        retry_delay = 2 # Initial backoff seconds

        while True:
            try:
                # Immediate local startup lines
                if local_greet:
                    local_greet = False
                    from core.utils import speak_local
                    import random
                    greetings = [
                        "Systems online, sir. Initialising mainframe connection.",
                        "All systems nominal. Welcome back, sir.",
                        "Good to see you again, sir. Booting core protocols.",
                        "Powering up, sir. Stand by for neural link.",
                        "JARVIS reporting for duty. Connection sequence initiated."
                    ]
                    greet = random.choice(greetings)
                    self.ui.write_log("SYS: Booting J.A.R.V.I.S. Core...")
                    self.ui.write_log("SYS: Local systems initialised.")
                    speak_local(greet)
                    self.ui.write_log("SYS: Wake word system active.")
                
                print(f"[JARVIS] Connecting (Retry delay: {retry_delay}s)...")
                self.ui.set_state("THINKING")
                if not first_run:
                    self.ui.write_log("SYS: Reconnecting to Gemini...")
                
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_running_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=100)
                    self.detection_queue = asyncio.Queue()

                    print("[JARVIS] Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online. Ready to help.")
                    
                    # Connection established, reset backoff
                    retry_delay = 2

                    tg.create_task(self.audio_engine.send_realtime_loop())
                    tg.create_task(self.audio_engine.listen_loop())
                    tg.create_task(self.audio_engine.detection_loop())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self.audio_engine.play_loop())

                    # Startup Briefing Trigger (Delayed for setup)
                    if first_run:
                        first_run = False
                        await asyncio.sleep(4) # Wait for audio and background systems
                        await session.send_client_content(
                            turns={"parts": [{"text": "System call: Perform 'daily_briefing' for Sahil now."}]},
                            turn_complete=True
                        )
                    
                    # Ensure the loop within TaskGroup doesn't exit immediately unless exception occurs
                    while True:
                        await asyncio.sleep(1)

            except Exception as e:
                print(f"[JARVIS] Connection error: {e}")
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
