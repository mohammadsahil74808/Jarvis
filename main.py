from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.genai import types
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import sys
import socket
import traceback

from ui import JarvisUI
from core.config import (
    get_base_dir, get_config, get_api_key, get_gemini_client,
    BASE_DIR, API_CONFIG_PATH, PROMPT_PATH,
    LIVE_MODEL, CHANNELS, SEND_SAMPLE_RATE,
    RECEIVE_SAMPLE_RATE, CHUNK_SIZE
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

def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools. "
            "Never simulate results — always call the appropriate tool."
        )

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
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ {e}")

def _index_conversation_async(user_text: str, jarvis_text: str) -> None:
    if not user_text.strip() and not jarvis_text.strip():
        return
    combined = f"User: {user_text}\nJarvis: {jarvis_text}"
    try:
        from memory.semantic_memory import add_semantic_memory
        add_semantic_memory(combined)
    except Exception as e:
        print(f"[Memory] ⚠️ Indexing: {e}")


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
        self._last_wake_time = 0

        from agent.tool_executor import ToolExecutor
        from core.audio_engine import AudioEngine
        self.tool_executor  = ToolExecutor(self, widgets_ok=False)
        self.audio_engine   = AudioEngine(self)
        self.ui.on_text_command = self._on_text_command

        # ── FIX 5: AppWatcher starts 15s after boot (not immediately) ──
        from core.app_watcher import AppWatcher
        self.app_watcher = AppWatcher(callback=self._on_app_activity)
        self.ui.root.after(15000, self.app_watcher.start)

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
                    self.detector = ClapDetector()
                    print("[JARVIS] Basic Clap Detector loaded")
            except Exception as e:
                print(f"[JARVIS] ClapDetector failed: {e}")
                self.detector     = None
                self.clap_enabled = False
        else:
            self.detector = None

        # ── Wake Word ──────────────────────────────────────────────────
        self.wake_detector     = None
        self.wake_word_enabled = config.get("wake_word_activation", True)
        if self.wake_word_enabled:
            threading.Thread(target=self._load_wake_detector, daemon=True).start()

        # ── Session state ──────────────────────────────────────────────
        self.session_context = {
            "last_app": None, "last_query": None,
            "last_file": None, "last_action": None, "last_tool": None
        }
        self._preloaded_memory = ""
        self.system_vitals     = {"cpu": 0, "ram": 0, "battery": None}
        self.active_plan       = None
        self.screen_context    = None
        self.memory_executor   = ThreadPoolExecutor(max_workers=1)
        self.usage_tracker     = None
        self.predictive_engine = None
        self.proactive_engine  = None
        self._profile_manager  = None
        self._personal_context = None
        self._companion_engine = None
        self._cached_config    = None
        self._config_dirty     = True

        # ── Lazy background init after 5s ──────────────────────────────
        self.ui.root.after(5000, self._background_lazy_init)

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

    @property
    def companion_engine(self):
        if self._companion_engine is None:
            from emotion.companion_engine import get_companion_engine
            self._companion_engine = get_companion_engine(self)
        return self._companion_engine

    # ─────────────────────────────────────────────────────────────
    def _background_lazy_init(self):
        config = _get_config()

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
        threading.Thread(target=_load_whisper, daemon=True).start()

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
        threading.Thread(target=_load_predictive, daemon=True).start()
        self.ui.root.after(5000, self._prediction_loop)

        def _load_proactive():
            try:
                ProactiveEngine = _lazy_proactive()
                history_path    = BASE_DIR / "memory" / "proactive_history.json"
                self.proactive_engine = ProactiveEngine(self, history_path)
                self.proactive_engine.start()
                self.ui.write_log("SYS: Intelligence module active.")
            except Exception as e:
                print(f"[JARVIS] Proactive: {e}")
        threading.Thread(target=_load_proactive, daemon=True).start()

        def _preload_memory():
            try:
                from memory.memory_manager import load_memory, format_memory_for_prompt
                self._preloaded_memory = format_memory_for_prompt(load_memory())
            except Exception as e:
                print(f"[JARVIS] Memory preload: {e}")
        threading.Thread(target=_preload_memory, daemon=True).start()

        # ── FIX 6: Vitals 60s interval + only dirty when values change ──
        def _monitor_vitals():
            import psutil, time
            _last_cpu, _last_ram = 0, 0
            while True:
                try:
                    new_cpu = psutil.cpu_percent(interval=0.1)
                    new_ram = psutil.virtual_memory().percent
                    if abs(new_cpu - _last_cpu) > 10 or abs(new_ram - _last_ram) > 5:
                        self.system_vitals["cpu"] = new_cpu
                        self.system_vitals["ram"] = new_ram
                        self._config_dirty = True
                        _last_cpu, _last_ram = new_cpu, new_ram
                    bat = psutil.sensors_battery()
                    if bat:
                        self.system_vitals["battery"] = {
                            "percent": bat.percent,
                            "plugged":  bat.power_plugged
                        }
                except Exception:
                    pass
                time.sleep(60)   # Was 30 — now 60s
        threading.Thread(target=_monitor_vitals, daemon=True).start()

        def _load_rag_core():
            try:
                from rag_core import get_rag_engine
                engine = get_rag_engine()
                engine.start_background_jobs()
                print("[JARVIS] RAG Core initialized and Watchdog started.")
            except Exception as e:
                print(f"[JARVIS] RAG Core Init Error: {e}")
        threading.Thread(target=_load_rag_core, daemon=True).start()

        self.ui.root.after(900000, self._companion_heartbeat)

    def _companion_heartbeat(self):
        if self.companion_engine:
            msg = self.companion_engine.check_proactive()
            if msg:
                self.notify(msg, voice=True)
        self.ui.root.after(900000, self._companion_heartbeat)

    def _on_app_activity(self, opened, closed):
        if opened:
            self.session_context["last_app"]    = opened[0]
            self.session_context["last_action"] = "opened"
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

        sys_prompt = _load_system_prompt()
        now        = datetime.now()
        time_ctx   = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {now.strftime('%A, %B %d, %Y — %I:%M %p')}\n\n"
        )

        ctx_parts = []
        for k, label in [("last_app","Last app"),("last_query","Last query"),
                         ("last_file","Last file"),("last_action","Last action")]:
            v = self.session_context.get(k)
            if v: ctx_parts.append(f"{label}: {v}")

        session_ctx_str = ""
        if ctx_parts:
            session_ctx_str = "[SESSION CONTEXT]\n" + "\n".join(ctx_parts) + "\n\n"

        plan_str = ""
        if self.active_plan:
            steps = []
            for i, s in enumerate(self.active_plan, 1):
                steps.append(f"{i}. {'[DONE]' if s['done'] else '[PENDING]'} {s['step']}")
            plan_str = "[ACTIVE PLAN]\n" + "\n".join(steps) + "\n\n"

        screen_ctx_str = ""
        if self.screen_context:
            screen_ctx_str = f"[SCREEN CONTEXT]\n{self.screen_context}\n\n"

        parts = [time_ctx]
        if session_ctx_str: parts.append(session_ctx_str)
        if plan_str:         parts.append(plan_str)
        if screen_ctx_str:   parts.append(screen_ctx_str)
        if mem_str:          parts.append(mem_str)

        user_ctx     = self.personal_context.get_context_summary()
        emotion_ctx  = self.companion_engine.get_emotional_context()
        parts.append(f"[USER PERSONAL CONTEXT]\n{user_ctx}\n")
        parts.append(f"{emotion_ctx}\n")

        v = self.system_vitals
        vitals = f"[SYSTEM: CPU {v.get('cpu',0):.0f}%, RAM {v.get('ram',0):.0f}%"
        if v.get("battery"):
            bat = v["battery"]
            vitals += f", Battery {bat['percent']}% ({'Plugged' if bat['plugged'] else 'Battery'})"
        vitals += "]\n"
        parts.append(vitals)
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
                                self.memory_executor.submit(
                                    _update_memory_async, self, full_in, full_out)
                                self.memory_executor.submit(
                                    _index_conversation_async, full_in, full_out)
                                caring = self.companion_engine.process_interaction(full_in)
                                if caring:
                                    self.ui.root.after(2000,
                                        lambda m=caring: self.notify(m, voice=True))

                    if response.tool_call:
                        self.tool_call_pending = True
                        try:
                            fn_responses = []
                            for fc in response.tool_call.function_calls:
                                print(f"[JARVIS] Tool: {fc.name}")
                                fr = await self.tool_executor.execute(fc)
                                fn_responses.append(fr)
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
        client      = get_gemini_client()
        first_run   = True
        local_greet = True
        retry_delay = 2

        while True:
            try:
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

                    if first_run:
                        first_run = False
                        # ── FIX 2: was 4s — now 1s ──
                        await asyncio.sleep(1)
                        await session.send_client_content(
                            turns={"parts": [{"text":
                                "System call: Perform 'daily_briefing' for Sahil now."}]},
                            turn_complete=True
                        )

                    while True:
                        await asyncio.sleep(1)

            except Exception as e:
                print(f"[JARVIS] Connection error: {e}")
                self.ui.write_log(
                    f"SYS: Connection lost. Reconnecting in {retry_delay}s...")
                self.ui.set_state("INITIALISING")
                self.session = None
                self.set_speaking(False)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)


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

    def runner():
        ui.wait_for_api_key()
        jarvis    = JarvisLive(ui)
        ui.jarvis = jarvis
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\nShutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
