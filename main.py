from __future__ import annotations
import os
os.environ["PYTHONWARNINGS"] = "ignore"
import warnings
warnings.filterwarnings("ignore")

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.genai import types
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
import socket
import traceback
import time

from ui import JarvisUI
from core.config import (
    get_config, get_api_key, get_gemini_client,
    rotate_api_key,
    BASE_DIR, PROMPT_PATH,
    LIVE_MODEL
)



# ── Lazy imports ───────────────────────────────────────────────
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

def _load_system_prompt(persona="jarvis") -> str:
    try:
        from core.config import BASE_DIR
        prompt_path = BASE_DIR / "core" / f"{persona}_prompt.txt"
        if not prompt_path.exists() and persona == "jarvis":
            prompt_path = PROMPT_PATH
            
        return prompt_path.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools. "
            "Never simulate results — always call the appropriate tool."
        )

# Global process-singleton socket used to ensure only one JARVIS instance runs at a time
# and to receive wake-up pings from external triggers.
_shared_udp_socket = None


def startup_check():
    key = _get_api_key()
    if not key or len(key.strip()) < 10:
        print("=" * 50)
        print("❌ JARVIS: API key missing hai!")
        print("   Pehle setup screen mein key enter karo.")
        print("=" * 50)
        sys.exit(1)


# ── Memory helpers ─────────────────────────────────────────────
def _update_memory_async(jarvis, user_text: str, jarvis_text: str) -> None:
    user_text   = (user_text   or "").strip()
    jarvis_text = (jarvis_text or "").strip()
    try:
        from intelligence.interaction_layer import get_interaction_layer
        get_interaction_layer().track_interaction(user_text, jarvis_text, jarvis)
    except Exception as e:
        print(f"[Interaction Layer] Error: {e}")

    last_input = jarvis.state.get_session("last_memory_input")
    if len(user_text) < 5 or user_text == last_input:
        return
    jarvis.state.update_session("last_memory_input", user_text)
    try:
        from memory.memory_manager import should_extract_memory, extract_memory, update_memory
        api_key = _get_api_key()
        if not should_extract_memory(user_text, jarvis_text, api_key):
            return
        data = extract_memory(user_text, jarvis_text, api_key)
        if data:
            # --- MEMORY-WRITE GUARD ---
            source = "conversation"
            last_tool = jarvis.state.get_session("last_tool")
            if last_tool in ("web_search", "browser_control", "browser_agent", "file_manager", "vision_action", "code_helper"):
                source = "tool_result"
            
            if source != "conversation":
                print(f"[Memory Guard] Flagged potentially untrusted memory extraction from {last_tool}. Skipping silent write: {data}")
                jarvis.ui.write_log(f"SYS: [Memory Guard] Blocked silent memory write from {last_tool}.")
                return
                
            update_memory(data)
            jarvis._config_dirty = True
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ {e}")

def _index_conversation_async(jarvis, user_text: str, jarvis_text: str) -> None:
    if not user_text.strip() and not jarvis_text.strip():
        return
    combined = f"User: {user_text}\nJarvis: {jarvis_text}"
    try:
        if hasattr(jarvis, "rag_ready"):
            jarvis.rag_ready.wait()
        from memory.semantic_memory import add_semantic_memory
        add_semantic_memory(combined)
    except Exception as e:
        print(f"[Memory] ⚠️ Indexing: {e}")


from agent.tool_definitions import TOOL_DECLARATIONS
_CACHED_TOOLS = [{"function_declarations": TOOL_DECLARATIONS}]


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        from typing import Any
        self.ui             = ui
        self.session: Any   = None
        self.audio_in_queue: Any = None
        self.out_queue: Any      = None
        self._loop: Any          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self._last_wake_time: float = 0.0

        from agent.tool_executor import ToolExecutor
        from core.audio_engine import AudioEngine
        self.tool_executor  = ToolExecutor(self)
        self.audio_engine   = AudioEngine(self)
        self.ui.on_text_command = self._on_text_command

        # AppWatcher starts immediately (no artificial delay)
        from core.app_watcher import AppWatcher
        self.app_watcher = AppWatcher(callback=self._on_app_activity)
        self.ui.root.after(0, self.app_watcher.start)

        config = _get_config()

        # ── Clap Activation ────────────────────────────────────────────
        self.clap_enabled = config.get("clap_activation", False)

        # ── Whisper Offline Fallback (faster-whisper) ──────────────────
        self.whisper_fb = None

        if self.clap_enabled:
            try:
                # ── FIX 4: Only load ML model if clap_model.pth exists ──
                _ml_path = BASE_DIR / "actions" / "clap_cnn" / "clap_model.pth"
                if _ml_path.exists():
                    from core.clap_detector_ml import MLClapDetector
                    self.detector = MLClapDetector()
                    print("[JARVIS] ML Clap Detector loaded")
                else:
                    from core.clap_detector import ClapDetector
                    self.detector: Any = ClapDetector() # type: ignore
                    print("[JARVIS] Basic Clap Detector loaded")
            except Exception as e:
                print(f"[JARVIS] ClapDetector failed: {e}")
                self.detector: Any = None # type: ignore
                self.clap_enabled = False
        else:
            self.detector: Any = None # type: ignore

        # ── Wake Word ──────────────────────────────────────────────────
        self.wake_detector     = None
        self.wake_word_enabled = config.get("wake_word_activation", True)
        if self.wake_word_enabled:
            threading.Thread(target=self._load_wake_detector, daemon=True).start()

        # ── Session state ──────────────────────────────────────────────
        from core.state import JarvisState
        self.state = JarvisState()
        
        self._preloaded_memory = ""
        self.vision_service    = None
        self.memory_executor   = ThreadPoolExecutor(max_workers=2)
        self.rag_ready         = threading.Event()
        self.usage_tracker     = None
        self.predictive_engine = None
        self.proactive_engine  = None
        self._profile_manager  = None
        self._personal_context = None
        self._cached_config    = None
        self._config_dirty     = True
        self._force_restart    = False

        # ── Lazy background init immediately ──
        self.ui.root.after(0, self._background_lazy_init)

        # ── UDP Wake Listener ──────────────────────────────────────────
        self._start_udp_listener()

    # ─────────────────────────────────────────────────────────────
    def _start_udp_listener(self):
        def _listen():
            global _shared_udp_socket
            sock = _shared_udp_socket
            if sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.bind(("127.0.0.1", 9999))
                except Exception as e:
                    print(f"[JARVIS] UDP bind error (tests): {e}")
                    return
            try:
                while True:
                    data, _ = sock.recvfrom(1024)
                    if data.decode("utf-8") == "WAKE":
                        self.ui.root.after(0, self._handle_wake)
            except Exception as e:
                print(f"[JARVIS] UDP error: {e}")
            finally:
                if _shared_udp_socket is None:
                    sock.close()
        threading.Thread(target=_listen, daemon=True).start()

    def _handle_wake(self):
        try:
            import time
            curr = time.time()
            if curr - self._last_wake_time < 3.0:
                return
            self._last_wake_time = curr

            self.ui.root.deiconify()
            self.ui.root.lift()
            self.ui.root.focus_force()
            self.ui.set_mute(False)
            from core.utils import speak_local
            speak_local("At your service, sir.")
            self.ui.write_log("SYS: Global activation triggered.")
        except Exception as e:
            print(f"[JARVIS] Wake error: {e}")

    # ─────────────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────────
    def _background_lazy_init(self):
        config = _get_config()

        def _staggered_start(fn, delay):
            def runner():
                if delay > 0:
                    time.sleep(delay)
                fn()
            threading.Thread(target=runner, daemon=True).start()

        import os
        if os.environ.get("JARVIS_LATENCY_DEBUG"):
            def _log_startup_metrics():
                try:
                    import psutil, time
                    p = psutil.Process()
                    t0 = time.time()
                    while time.time() - t0 < 30:
                        time.sleep(1.0)
                        cpu = p.cpu_percent(interval=None)
                        rss = p.memory_info().rss / 1e6
                        print(f"[LATENCY] startup t={time.time()-t0:.1f}s CPU={cpu:.1f}% RAM={rss:.1f}MB")
                except Exception as e:
                    print(f"[LATENCY] Startup metric error: {e}")
            threading.Thread(target=_log_startup_metrics, daemon=True, name="LatencyDebugStartup").start()

        def _load_whisper():
            try:
                print("[JARVIS] Loading Faster-Whisper base.en model in background...")
                from faster_whisper import WhisperModel
                # Load on CPU with int8 quantization for high speed and low memory usage
                model = WhisperModel("base.en", device="cpu", compute_type="int8")
                
                # Perform a lightweight warm-up inference (100ms of zeros) to pre-fill model execution cache
                import numpy as np
                dummy_audio = np.zeros(1600, dtype=np.float32)
                list(model.transcribe(dummy_audio, beam_size=1)[0])
                
                self.whisper_fb = model
                print("[JARVIS] Faster-Whisper base.en model loaded, warmed up, and ready.")
            except Exception as e:
                print(f"[JARVIS] Faster-Whisper load failed: {e}")
                self.whisper_model = None

        def _load_predictive():
            try:
                from core.usage_tracker import UsageTracker
                from core.predictive_engine import PredictiveEngine
                log_path = BASE_DIR / "memory" / "usage_log.json"
                self.usage_tracker    = UsageTracker(log_path)
                self.predictive_engine = PredictiveEngine(log_path)
                self.predictive_engine.set_mode(config.get("predictive_mode", True))
            except Exception as e:
                print(f"[JARVIS] Predictive: {e}")

        def _preload_memory():
            try:
                from memory.memory_manager import load_memory, format_memory_for_prompt
                self._preloaded_memory = format_memory_for_prompt(load_memory())
            except Exception as e:
                print(f"[JARVIS] Memory preload: {e}")

        def _load_vision_service():
            from vision.service import VisionService
            try:
                self.vision_service = VisionService(config, on_context=self._on_screen_context)
                self.vision_service.start()
                self.ui.write_log("SYS: Persistent vision context active.")
            except Exception as e:
                print(f"[JARVIS] Vision Service: {e}")

        def _load_rag_core():
            try:
                from rag_core import get_rag_engine
                engine = get_rag_engine()
                engine.start_background_jobs()
                print("[JARVIS] RAG Core initialized and Watchdog started.")
                self.rag_ready.set()
            except Exception as e:
                print(f"[JARVIS] RAG Core Init Error: {e}")

        def _load_proactive():
            try:
                ProactiveEngine = _lazy_proactive()
                history_path    = BASE_DIR / "memory" / "proactive_history.json"
                self.proactive_engine = ProactiveEngine(self, history_path)
                self.proactive_engine.start()
                self.ui.write_log("SYS: Intelligence module active.")
            except Exception as e:
                print(f"[JARVIS] Proactive: {e}")

        def _load_mcp():
            try:
                print("[JARVIS] Initializing MCP Client Integration...")
                from mcp_client.manager import setup_mcp_integration
                import asyncio
                mcp_tools = asyncio.run(setup_mcp_integration())
                if mcp_tools:
                    print(f"[JARVIS] Loaded {len(mcp_tools)} MCP tools into background MCP Manager.")

                    # CRITICAL: MCP tools were previously only cached in MCPManager and
                    # never merged into _CACHED_TOOLS, which is the ONLY tool list ever
                    # sent to Gemini Live (`tools=_CACHED_TOOLS` in _build_config). That
                    # meant Gemini never knew these tools existed and could never call
                    # them, no matter how well tool_executor's MCP dispatch worked.
                    # Merge them in now and restart the session so the live connection
                    # picks up the full tool list (same mechanism already used for
                    # persona switches).
                    existing_names = {t.get("name") for t in TOOL_DECLARATIONS}
                    new_mcp_tools = [t for t in mcp_tools if t.get("name") not in existing_names]
                    if new_mcp_tools:
                        _CACHED_TOOLS[0]["function_declarations"] = TOOL_DECLARATIONS + new_mcp_tools
                        self._config_dirty = True
                        if self.session:
                            self._force_restart = True
                        print(f"[JARVIS] Registered {len(new_mcp_tools)} MCP tools with Gemini Live tool schema.")
            except Exception as e:
                print(f"[JARVIS] MCP Init Error: {e}")

        # ── Unified Background Scheduler ──
        def _shared_scheduler_loop():
            import psutil, time  # type: ignore
            _last_cpu, _last_ram = 0, 0
            ticks = 0
            while True:
                time.sleep(60)
                ticks += 1
                
                # 1. Vitals (every 1 min)
                try:
                    new_cpu = psutil.cpu_percent(interval=0.1)
                    new_ram = psutil.virtual_memory().percent
                    if abs(new_cpu - _last_cpu) > 10 or abs(new_ram - _last_ram) > 5:
                        self.state.update_vitals(new_cpu, new_ram)
                        self._config_dirty = True
                        _last_cpu, _last_ram = new_cpu, new_ram
                    bat = psutil.sensors_battery()
                    if bat:
                        self.state.update_vitals(new_cpu, new_ram, {
                            "percent": bat.percent,
                            "plugged":  bat.power_plugged
                        })
                except Exception:
                    pass

                # 2. Proactive Engine tick (every 1 min)
                if self.proactive_engine and getattr(self.proactive_engine, 'running', False):
                    try:
                        self.proactive_engine._loop_tick()
                    except Exception:
                        pass

                # 3. Prediction loop (every 10 min)
                if ticks % 10 == 0:
                    try:
                        self._prediction_loop()
                    except Exception:
                        pass

        # ── Staggered background loading to prevent CPU/RAM spike at startup ──
        _staggered_start(_load_whisper, 0.0)
        _staggered_start(_load_predictive, 0.5)
        _staggered_start(_preload_memory, 1.0)
        _staggered_start(_load_rag_core, 1.5)
        _staggered_start(_load_vision_service, 2.0)
        _staggered_start(_load_proactive, 2.5)
        _staggered_start(_load_mcp, 3.0)
        
        # Start shared scheduler loop in background
        threading.Thread(target=_shared_scheduler_loop, daemon=True, name="SharedScheduler").start()

    def _on_screen_context(self, context):
        try:
            self.state.screen_context = context.to_prompt()
            self._config_dirty = True
        except Exception as e:
            print(f"[JARVIS] Screen context update: {e}")

    def get_screen_context(self):
        if self.vision_service:
            return self.vision_service.latest()
        return None

    def _on_app_activity(self, opened, closed):
        if opened:
            self.state.update_session("last_app", opened[0])
            self.state.update_session("last_action", "opened")
            self._config_dirty = True
        if closed:
            self._config_dirty = True

    def notify(self, text: str, voice: bool = True):
        if getattr(self, "tool_call_pending", False) or self._is_speaking:
            return
        if text.startswith("["):
            self.speak(text)
            return
        self.ui.show_suggestion(text)
        if voice and not self._is_speaking and not self.ui.muted:
            self.speak(f"Sir, {text}")

    def write_log(self, text: str):
        self.ui.write_log(text)

    def _load_wake_detector(self):
        try:
            from core.wake_detector import WakeWordDetector
            self.wake_detector = WakeWordDetector()
            self.ui.write_log("SYS: openWakeWord system ready hai.")
        except Exception as e:
            print(f"[JARVIS] WakeWord Error: {e}")
            self.wake_word_enabled = False

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        # ── Sanitize input to prevent Gemini Live 1011 WebSocket crash ──
        text = text.strip()
        # Strip unmatched leading/trailing quotes
        if text.startswith('"') and not text.endswith('"'):
            text = text[1:].strip()
        elif text.endswith('"') and not text.startswith('"'):
            text = text[:-1].strip()
        if text.startswith("'") and not text.endswith("'"):
            text = text[1:].strip()
        elif text.endswith("'") and not text.startswith("'"):
            text = text[:-1].strip()
        # Expand very short single-word affirmatives into safe phrases
        # (bare "ha", "haan", "yes", etc. can cause 1011 on Gemini Live)
        _AFFIRM_MAP = {
            "ha": "haan, proceed karo",
            "haan": "haan, proceed karo",
            "yes": "yes, proceed",
            "ok": "ok, proceed",
            "sure": "sure, go ahead",
            "proceed": "please proceed",
            "confirm": "yes, confirmed",
            "go": "go ahead",
        }
        if text.lower() in _AFFIRM_MAP:
            text = _AFFIRM_MAP[text.lower()]
        # Ensure minimum safe length
        if len(text) < 2:
            return
        from core.local_router import route_command
        if route_command(text, self):
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )


    def _prediction_loop(self):
        if self.predictive_engine and self.predictive_engine.predictive_mode:
            suggestion = self.predictive_engine.get_suggestion()
            if suggestion:
                self.ui.show_suggestion(suggestion["text"])

    def interrupt_speaking(self):
        with self._speaking_lock:
            was_speaking = self._is_speaking
            self._is_speaking = False
            
        if was_speaking:
            while not self.audio_in_queue.empty():
                try:
                    self.audio_in_queue.get_nowait()
                except Exception:
                    break
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
                
            if self._loop and self.session:
                asyncio.run_coroutine_threadsafe(
                    self.session.send_client_content(
                        turns={"parts": [{"text": "User interrupted."}]},
                        turn_complete=True
                    ),
                    self._loop
                )

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
        if getattr(self, "tool_call_pending", False) or self._is_speaking:
            return

        # Sanitize text string to prevent Gemini Live 1011 JSON framing error
        text = text.strip()
        if text.startswith('"') and not text.endswith('"'):
            text = text[1:].strip()
        elif text.endswith('"') and not text.startswith('"'):
            text = text[:-1].strip()

        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: Exception | str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def get_user_context(self):
        return self.personal_context.get_context_summary()

    # ─────────────────────────────────────────────────────────────
    # BUILD CONFIG
    # ─────────────────────────────────────────────────────────────
    def _build_config(self) -> types.LiveConnectConfig:
        if not self._config_dirty and self._cached_config:
            return self._cached_config

        from datetime import datetime
        mem_str = self._preloaded_memory or ""
        if not mem_str:
            try:
                from memory.memory_manager import load_memory, format_memory_for_prompt
                mem_str = format_memory_for_prompt(load_memory())
            except Exception:
                pass

        persona = getattr(self.state, "active_persona", "jarvis")
        sys_prompt = _load_system_prompt(persona)
        now        = datetime.now()
        time_ctx   = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {now.strftime('%A, %B %d, %Y — %I:%M %p')}\n\n"
        )

        mem_parts = []
        for k in ["last_app", "last_file", "last_action", "last_query"]:
            v = self.state.get_session(k)
            if v:
                mem_parts.append(f"{k.replace('_', ' ').title()}: {v}")

        session_ctx_str = ""
        if mem_parts:
            session_ctx_str = "[SESSION CONTEXT]\n" + "\n".join(mem_parts) + "\n\n"

        plan_str = ""
        if self.state.active_plan:
            steps = []
            for i, s in enumerate(self.state.active_plan, 1):
                steps.append(f"{i}. {'[DONE]' if s['done'] else '[PENDING]'} {s['step']}")
            plan_str = "[ACTIVE PLAN]\n" + "\n".join(steps) + "\n\n"

        screen_ctx_str = ""
        if self.state.screen_context:
            screen_ctx_str = f"[SCREEN CONTEXT]\n{self.state.screen_context}\n\n"

        parts = [time_ctx]
        if session_ctx_str: parts.append(session_ctx_str)
        if plan_str:         parts.append(plan_str)
        if screen_ctx_str:   parts.append(screen_ctx_str)
        if mem_str:          parts.append(mem_str)

        user_ctx     = self.personal_context.get_context_summary()
        emotion_ctx  = self.proactive_engine.get_emotional_context() if self.proactive_engine else ""
        parts.append(f"[USER PERSONAL CONTEXT]\n{user_ctx}\n")
        parts.append(f"{emotion_ctx}\n")

        v = self.state.system_vitals
        vitals = f"[SYSTEM: CPU {v.get('cpu',0):.0f}%, RAM {v.get('ram',0):.0f}%"
        if v.get("battery"):
            bat = v["battery"]
            vitals += f", Battery {bat['percent']}% ({'Plugged' if bat['plugged'] else 'Battery'})"
        vitals += "]\n"
        parts.append(vitals)
        parts.append(sys_prompt)

        system_instruction_str = "\n".join(parts)
        # Hardcode Gemini context limit to ~1M tokens (approx 3.5M characters)
        if len(system_instruction_str) > 3500000:
            system_instruction_str = system_instruction_str[-3500000:]
            
        _genai, _types = _lazy_genai()
        voice_name = "Kore" if persona == "friday" else "Charon"
        config_obj = _types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction=system_instruction_str,
            tools=_CACHED_TOOLS,
            session_resumption=_types.SessionResumptionConfig(),
            speech_config=_types.SpeechConfig(
                voice_config=_types.VoiceConfig(
                    prebuilt_voice_config=_types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )
        self._cached_config = config_obj
        self._config_dirty  = False
        return config_obj

    # ─────────────────────────────────────────────────────────────
    # RECEIVE AUDIO
    # ─────────────────────────────────────────────────────────────
    async def _receive_audio(self):
        print("[JARVIS] Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    if hasattr(response, "text") and response.text:
                        pass # Text consumed via server_content transcription

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

                        if getattr(sc, "interrupted", False):
                            while not self.audio_in_queue.empty():
                                try:
                                    self.audio_in_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            self.set_speaking(False)

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
                                self.memory_executor.submit(
                                    _update_memory_async, self, full_in, full_out)
                                # Automatic blind conversation indexing disabled per persistent memory design
                                caring = self.proactive_engine.process_interaction(full_in) if self.proactive_engine else None
                                if caring:
                                    self.ui.root.after(2000,
                                        lambda: self.notify(caring, voice=True))

                    if response.tool_call:
                        self.tool_call_pending = True
                        try:
                            fn_responses = []
                            concurrent_tasks = []
                            
                            for fc in response.tool_call.function_calls:
                                print(f"[JARVIS] Tool: {fc.name}")
                                
                                if fc.name in ("website_builder", "app_builder"):
                                    from agent.task_queue import get_queue, TaskPriority
                                    goal_desc = f"Use {fc.name} with args: {fc.args}"
                                    get_queue().submit(goal=goal_desc, priority=TaskPriority.NORMAL, speak=self.speak)
                                    
                                    _, types = _lazy_genai()
                                    fn_responses.append(
                                        types.FunctionResponse(
                                            id=fc.id, name=fc.name,
                                            response={"result": f"Task '{fc.name}' dispatched to background. I will notify the user when done."}
                                        )
                                    )
                                else:
                                    concurrent_tasks.append(self.tool_executor.execute(fc))
                                    
                            if concurrent_tasks:
                                results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
                                for res in results:
                                    if isinstance(res, BaseException):
                                        print(f"[JARVIS] Tool Error: {res}")
                                    elif res is not None:
                                        fn_responses.append(res)  # type: ignore
                                        
                            await self.session.send_tool_response(
                                function_responses=fn_responses)
                            # ── FIX 3: was 0.5s — now 0.1s ──
                            await asyncio.sleep(0.1)
                        finally:
                            self.tool_call_pending = False

        except Exception as e:
            print(f"[JARVIS] Recv error: {e}")
            traceback.print_exc()
            raise

    # ─────────────────────────────────────────────────────────────
    # RUN
    # ─────────────────────────────────────────────────────────────
    async def run(self):
        first_run   = True
        local_greet = True
        retry_delay = 2

        while True:
            try:
                persona = getattr(self.state, "active_persona", "jarvis")
                client = get_gemini_client(persona)
                
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
                    speak_local(random.choice(greetings))
                    self.ui.write_log("SYS: Booting J.A.R.V.I.S. Core...")
                    self.ui.write_log("SYS: Local systems initialised.")

                print(f"[JARVIS] Connecting...")
                self.ui.set_state("THINKING")

                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session         = session
                    self._loop           = asyncio.get_running_loop()
                    self.audio_in_queue  = asyncio.Queue()
                    self.out_queue       = asyncio.Queue(maxsize=100)
                    self.detection_queue = asyncio.Queue()

                    print("[JARVIS] Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online. Ready to help.")
                    retry_delay = 2

                    tg.create_task(self.audio_engine.send_realtime_loop())
                    tg.create_task(self.audio_engine.listen_loop())
                    tg.create_task(self.audio_engine.detection_loop())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self.audio_engine.play_loop())

                    if getattr(self, "pending_greeting", None):
                        msg = self.pending_greeting
                        self.pending_greeting = None
                        await asyncio.sleep(0.5)
                        await session.send_client_content(
                            turns={"parts": [{"text": msg}]},
                            turn_complete=True
                        )

                    while True:
                        if self._force_restart:
                            self._force_restart = False
                            raise Exception("RESTART_SESSION")
                        await asyncio.sleep(0.1)

            except Exception as e:
                err_str = str(e).lower()
                if "restart_session" in err_str:
                    print("[JARVIS] Restarting session for new config...")
                    retry_delay = 0
                    await asyncio.sleep(0.5) # Let PortAudio clean up streams
                elif "429" in err_str or "quota" in err_str or "exhausted" in err_str:
                    print(f"[JARVIS] API Quota Exceeded! Switching API key...")
                    self.ui.write_log("SYS: API Quota Exceeded. Rotating key...")
                    rotate_api_key()
                    retry_delay = 0
                else:
                    print(f"[JARVIS] Connection error: {e}")
                    if hasattr(e, "exceptions"):
                        for idx, sub_err in enumerate(e.exceptions, 1):
                            print(f"[JARVIS]   Sub-exception {idx}: {type(sub_err).__name__}: {sub_err}")
                    self.ui.write_log(
                        f"SYS: Connection lost. Reconnecting in {retry_delay}s...")
                    retry_delay = min(retry_delay * 2, 30)
                    
                self.ui.set_state("INITIALISING")
                self.session = None
                self.set_speaking(False)
                if retry_delay > 0:
                    await asyncio.sleep(retry_delay)
                retry_delay = max(2, retry_delay) # Reset to at least 2 for next real error
    def shutdown(self):
        print("[JARVIS] Shutting down services...")
        if getattr(self, "vision_service", None):
            try:
                self.vision_service.stop()
                print("[JARVIS] Vision service stopped.")
            except Exception as e:
                print(f"[JARVIS] Vision stop error: {e}")

        if getattr(self, "proactive_engine", None):
            try:
                self.proactive_engine.stop()
                print("[JARVIS] Proactive engine stopped.")
            except Exception as e:
                print(f"[JARVIS] Proactive stop error: {e}")
                
        if getattr(self, "app_watcher", None):
            try:
                self.app_watcher.stop()
                print("[JARVIS] AppWatcher stopped.")
            except: pass
            
        if getattr(self, "audio_engine", None):
            try:
                self.audio_engine.stop()
            except: pass
            
        if getattr(self, "memory_executor", None):
            try:
                self.memory_executor.shutdown(wait=False)
            except: pass
            
        try:
            from jarvis.browser.browser_adapter import get_browser_adapter
            adapter = get_browser_adapter()
            if adapter is not None:
                adapter.shutdown()
                print("[JARVIS] Browser adapter shutdown completed.")
        except Exception as e:
            print(f"[JARVIS] Browser cleanup error: {e}")




# ─────────────────────────────────────────────────────────────
def main():
    global _shared_udp_socket
    try:
        _shared_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _shared_udp_socket.bind(("127.0.0.1", 9999))
    except OSError:
        try:
            wake_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            wake_sock.sendto(b"WAKE", ("127.0.0.1", 9999))
            wake_sock.close()
        except Exception:
            pass
        print("[JARVIS] An instance is already running. Sent wake signal. Exiting.")
        sys.exit(0)

    ui = JarvisUI("face.png")
    
    # Store reference so we can access it on exit
    _jarvis_instance = None

    def on_close():
        if _jarvis_instance:
            _jarvis_instance.shutdown()
        ui.root.quit()
        ui.root.destroy()

    ui.root.protocol("WM_DELETE_WINDOW", on_close)

    def runner():
        nonlocal _jarvis_instance
        ui.wait_for_api_key()
        jarvis    = JarvisLive(ui)
        ui.jarvis = jarvis
        _jarvis_instance = jarvis
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\nShutting down...")
            if _jarvis_instance is not None:
                _jarvis_instance.shutdown()
            ui.root.quit()

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()